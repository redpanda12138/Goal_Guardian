from sqlalchemy.orm import Session

from app.core.utils import *
from app.db.account_entities import *
from app.db.chat_entities import *
from app.db.sys_entities import *
from app.db.topic_entities import *
from app.models.account_models import *
from app.models.chat_models import *
from app.services.account_service import AccountService
from app.services.topic_service import TopicService

from app.ai.models import *
from app.ai import chat_ai
from app.core.azure_voice import *
from app.core.exceptions import *
from app.core.whisper_voice import whisper_processor
from datetime import datetime, timezone

MESSAGE_SYSTEM = "SYSTEM"


def _voice_to_text(speech_path: str) -> str:
    """语音转文字：优先使用 Whisper，避免依赖已注释的 Azure 模块。"""
    if not speech_path:
        return ""
    try:
        if getattr(whisper_processor, "pipe", None):
            text = whisper_processor.transcribe_audio(speech_path)
            return (text or "").strip()
    except Exception as e:
        from app.core.logging import logging
        logging.warning(f"Whisper 语音转写失败: {e}")
    return ""


# 读取data下 language_demo_map.json 生成对应字典
language_demo_map = {}
with open("data/language_demo_map.json", "r") as f:
    language_demo_map = json.load(f)


class ChatService:
    """聊天核心类，会调用account_service与topic_service, 反向不可以引用"""

    def __init__(self, db: Session):
        self.db = db
        self.account_service = AccountService(db)
        self.topic_service = TopicService(db)

    def get_settings_languages_example(self, language: str, account_id: str):
        """获取语言下的示例"""
        # 获取语言下的示例
        # 语言没有国家  所以去掉后面的国家后缀
        language = language.split("-")[0]
        return language_demo_map[language]

    def get_default_session(self, account_id: str):
        """获取用户的默认会话, 如果没有默认会话，就创建一个"""
        session = (
            self.db.query(MessageSessionEntity)
            .filter_by(
                account_id=account_id,
                is_default=1,
            )
            .order_by(MessageSessionEntity.create_time.desc())
            .first()
        )
        if not session:
            # 为用户创建一个默认的session
            return self.create_session(
                account_id,
            )
        return self.__convert_session_model(session)

    def get_session(self, session_id: str, account_id: str):
        """获取会话详情"""
        session = self.__get_and_check_session(session_id, account_id)
        # MAS：OA(goal_reviews) 为权威状态；定时 SOA 只写 OA，App 读的是 DB，需在打开会话时同步
        if session.type == "MAS":
            try:
                # 仅同步“最新 MAS 会话”，避免历史会话被当前 OA 状态覆盖
                latest_mas_session = (
                    self.db.query(MessageSessionEntity)
                    .filter_by(account_id=account_id, type="MAS")
                    .order_by(MessageSessionEntity.create_time.desc())
                    .first()
                )
                if latest_mas_session and latest_mas_session.id == session_id:
                    self._sync_mas_messages_from_oa_if_needed(session_id, account_id)
            except Exception as e:
                from app.core.logging import logging

                logging.warning(f"MAS sync from OA skipped/failed for session {session_id}: {e}")

        result = self.__convert_session_model(session)

        # 获取会话下的消息
        result["messages"] = self.get_session_messages(session_id, account_id, 1, 100)
        return result

    def _sync_mas_messages_from_oa_if_needed(self, session_id: str, account_id: str) -> None:
        """
        将 OA 中该患者的对话历史镜像到当前 MAS 会话的 DB 记录。
        解决：定时任务触发 SOA 后消息只存在于 OA，Chat 页仍显示旧 DB 内容的问题。
        """
        from app.services.mas.patient_mapping_service import PatientMappingService
        from app.services.mas.mas_gateway_service import MASGatewayService
        from app.core.logging import logging
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        mapping_service = PatientMappingService(self.db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)

        try:
            history_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "oa",
                    f"/conversation_history/{patient_id}",
                    method="GET",
                )
            )
        except Exception as e:
            logging.warning(f"MAS sync: OA conversation_history request failed: {e}")
            return

        status = history_data.get("status")
        if status == "not_found":
            return
        if status != "ok":
            logging.warning(f"MAS sync: OA returned status={status}")
            return

        chat_history = history_data.get("chat_history") or []
        if not chat_history:
            return

        def _norm_chain(msgs: list) -> list:
            out = []
            for m in msgs:
                role = (m.get("role") or "").lower()
                content = (m.get("content") or "").strip()
                if not content or role not in ("user", "assistant"):
                    continue
                out.append((role, content))
            return out

        oa_chain = _norm_chain(chat_history)

        db_rows = (
            self.db.query(MessageEntity)
            .filter(
                MessageEntity.session_id == session_id,
                MessageEntity.account_id == account_id,
                MessageEntity.deleted == 0,
            )
            .order_by(MessageEntity.sequence.asc(), MessageEntity.create_time.asc())
            .all()
        )

        db_chain = []
        for m in db_rows:
            if m.type == MessageType.ACCOUNT.value:
                db_chain.append(("user", (m.content or "").strip()))
            elif m.type == MessageType.SYSTEM.value:
                db_chain.append(("assistant", (m.content or "").strip()))

        # OA 规范化后无有效消息但 DB 已有内容时，勿清空 DB（否则下次 total=0 会重复拉 greeting）
        if not oa_chain and db_chain:
            logging.info(
                f"MAS sync: skip mirror (OA empty after norm, DB has messages) session={session_id}"
            )
            return

        if len(db_chain) == len(oa_chain) and all(
            a == b for a, b in zip(db_chain, oa_chain)
        ):
            return

        logging.info(
            f"MAS sync: mirroring OA -> DB session={session_id} patient={patient_id} "
            f"(oa_msgs={len(oa_chain)} db_msgs={len(db_chain)})"
        )

        self.db.query(MessageEntity).filter(
            MessageEntity.session_id == session_id,
            MessageEntity.account_id == account_id,
            MessageEntity.deleted == 0,
        ).update({"deleted": 1})
        self.db.commit()

        seq = 0
        for role, content in oa_chain:
            seq += 1
            if role == "user":
                self.db.add(
                    self.__add_account_message(account_id, session_id, content, seq, None)
                )
            else:
                self.db.add(
                    self.__add_system_message(session_id, account_id, content, "", seq)
                )
        self.db.commit()
        self.db.flush()
        self.__refresh_session_message_count(session_id)

    def get_session_greeting(self, session_id: str, account_id: str):
        """需要会话没有任何消息时，需要返回的问候语"""

        # 检查session是否存在
        session = self.__get_and_check_session(session_id, account_id)

        # 检查会话下是否已经有了消息
        self.__check_has_messages(session_id, account_id)

        # ========== MAS模式：触发MAS会话开始 ==========
        if session.type == "MAS":
            from app.services.mas.patient_mapping_service import PatientMappingService
            from app.services.mas.mas_gateway_service import MASGatewayService
            import asyncio
            
            mapping_service = PatientMappingService(self.db)
            patient_id = mapping_service.get_or_create_patient_id(account_id)
            
            # 触发SOA开始会话
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "soa",
                    "/trigger",
                    data={"patient_id": patient_id, "turn_index": 1}
                )
            )
            
            # 从OA获取第一条消息（需要等待一下让SOA处理完成）
            import time
            time.sleep(1)  # 等待SOA处理
            
            # 获取对话历史中的第一条消息
            history_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "oa",
                    f"/conversation_history/{patient_id}",
                    method="GET"
                )
            )
            
            if history_data.get("status") == "ok" and history_data.get("chat_history"):
                greeting_message = history_data["chat_history"][0].get("content", "Hello! How can I help you today?")
            else:
                greeting_message = "Hello! I'm your health coach. How are you feeling today?"
            
            sequence = self.__get_message_sequence(session_id)
            add_message = self.__add_system_message(session_id, account_id, greeting_message, "", sequence + 1)
            self.db.add(add_message)
            self.db.commit()
            self.db.flush()
            self.__refresh_session_message_count(session_id)
            return self.initMessageResult(add_message)
        
        # ========== 原有逻辑（保留） ==========
        # 区分自由聊天与话题聊天
        if session.type == "CHAT":
            language = self.account_service.get_account_target_language(account_id)
            result = chat_ai.invoke_greet(GreetParams(language=language))
        elif session.type == "TOPIC":
            topic_greet_params = self.topic_service.get_topic_greet_params(session.id)
            result = chat_ai.topic_invoke_greet(topic_greet_params)

        sequence = self.__get_message_sequence(session_id) 

        add_message = self.__add_system_message(session_id, account_id, result, "", sequence + 1)
        self.db.add(add_message)
        self.db.commit()
        self.db.flush()
        self.__refresh_session_message_count(session_id)
        return self.initMessageResult(add_message)

    def send_session_message(self, session_id: str, dto: ChatDTO, account_id: str):
        """发送消息"""
        # 如果有file_name却没有message，需要解析出message
        if not dto.file_name and not dto.message:
            raise Exception("Message or file_name is required")
        
        session = self.__get_and_check_session(session_id, account_id)

        account_settins = (
            self.db.query(AccountSettingsEntity)
            .filter_by(account_id=account_id)
            .first()
        )
        target_language = account_settins.target_language
        if dto.message:
            send_message_content = dto.message
        else:
            send_message_content = _voice_to_text(voice_file_get_path(dto.file_name))

        # 获取前面的sequence
        sequence = self.__get_message_sequence(session_id)

        add_account_message = self.__add_account_message(
            account_id, session_id, send_message_content, sequence + 1, dto.file_name
        )

        send_message_id = add_account_message.id
        message_history = (
            self.db.query(MessageEntity)
            .filter(MessageEntity.session_id == session_id)
            .order_by(MessageEntity.create_time.desc())
            .slice(0, 5)
            .all()
        )
        messages = []
        for message in reversed(message_history):
            if message.type == MessageType.SYSTEM.value:
                messages.append({"role": "assistant", "content": message.content})
            else:
                messages.append({"role": "user", "content": message.content})
        
        # 补充上用户新加的这个
        messages.append({"role": "user", "content": send_message_content})

        completed = False
        if session.type == 'CHAT':
            speech_role_name = account_settins.speech_role_name
            styles = []
            if speech_role_name:
                voice_role_config = get_azure_voice_role_by_short_name(speech_role_name)
                styles = voice_role_config["style_list"]
            message_params = MessageParams(
                language=target_language, name=Config.AI_NAME, messages=messages, styles=styles
            )
            invoke_result = chat_ai.invoke_message(message_params)
        elif session.type == 'TOPIC':
            topic_message_params = self.topic_service.get_topic_message_params(session.id)
            topic_message_params.messages = messages
            invoke_result = chat_ai.topic_invoke_message(topic_message_params)
            completed = invoke_result.completed

        add_system_message = self.__add_system_message(
            session_id,
            account_id,
            invoke_result.message,
            invoke_result.message_style,
            sequence + 2,
        )
        self.db.add(add_account_message)
        self.db.add(add_system_message)
        self.db.commit()
        self.db.flush()
        self.__refresh_session_message_count(session_id)
        return {
            "data": invoke_result.message,
            "id": add_system_message.id,
            "session_id": session_id,
            "send_message_id": send_message_id,
            "send_message_content": send_message_content,
            "create_time": date_to_str(add_system_message.create_time),
            "completed": completed,
        }

    def send_mas_session_message(self, session_id: str, dto: ChatDTO, account_id: str):
        """
        MAS对话模式：发送消息到MAS服务
        
        原逻辑：send_session_message 方法保留用于CHAT和TOPIC类型
        """
        from app.services.mas.patient_mapping_service import PatientMappingService
        from app.services.mas.mas_gateway_service import MASGatewayService
        import asyncio
        
        # 检查session是否存在
        session = self.__get_and_check_session(session_id, account_id)
        if session.type != 'MAS':
            raise Exception("Session type is not MAS")
        
        # 获取patient_id
        mapping_service = PatientMappingService(self.db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 处理消息内容（语音转文字或直接使用文本）
        account_settings = (
            self.db.query(AccountSettingsEntity)
            .filter_by(account_id=account_id)
            .first()
        )
        target_language = account_settings.target_language if account_settings else "en-US"
        
        if dto.message:
            send_message_content = dto.message
        else:
            send_message_content = _voice_to_text(voice_file_get_path(dto.file_name))
        
        # 获取当前会话状态，确定turn_index
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 获取当前会话状态
        try:
            status_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "oa",
                    f"/session_status/{patient_id}",
                    method="GET"
                )
            )
            current_turn_index = status_data.get("turn_index", 1)
            session_status = status_data.get("session_status", "active")
            
            from app.core.logging import logging
            logging.info(f"📊 MAS session status check: patient_id={patient_id}, turn_index={current_turn_index}, session_status={session_status}")
            
            # 如果会话已结束，直接返回结束消息
            if session_status == "completed" or current_turn_index >= 15:
                logging.warning(f"⚠️ Session is completed for patient {patient_id}: turn_index={current_turn_index}, session_status={session_status}")
                # 保存用户消息到数据库
                sequence = self.__get_message_sequence(session_id)
                add_account_message = self.__add_account_message(
                    account_id, session_id, send_message_content, sequence + 1, dto.file_name
                )
                send_message_id = add_account_message.id
                self.db.add(add_account_message)
                self.db.flush()
                
                # 即使会话已结束，也要保存user消息到OA，以便MMA可以提取
                try:
                    result = loop.run_until_complete(
                        MASGatewayService.call_mas_service(
                            "oa",
                            "/receive_user_message",
                            data={
                                "patient_id": patient_id,
                                "user_input": send_message_content,
                                "turn_index": current_turn_index
                            }
                        )
                    )
                    if result.get("status") == "ok":
                        logging.info(f"✅ Saved user message to OA for patient {patient_id} (session completed): {result}")
                    else:
                        logging.warning(f"⚠️ OA returned non-ok status: {result}")
                except Exception as e:
                    import traceback
                    logging.error(f"❌ Failed to save user message to OA (session completed): {e}")
                    logging.error(f"Traceback: {traceback.format_exc()}")
                
                # 返回会话结束消息
                end_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
                sequence = self.__get_message_sequence(session_id)
                add_system_message = self.__add_system_message(
                    session_id,
                    account_id,
                    end_message,
                    "",
                    sequence + 1,
                )
                
                self.db.add(add_account_message)
                self.db.add(add_system_message)
                self.db.commit()
                self.db.flush()
                self.__refresh_session_message_count(session_id)
                self._mark_mas_session_completed(session_id, account_id)

                return {
                    "data": end_message,
                    "id": add_system_message.id,
                    "session_id": session_id,
                    "send_message_id": send_message_id,
                    "send_message_content": send_message_content,
                    "create_time": date_to_str(add_system_message.create_time),
                    "completed": True,
                }
            
            if current_turn_index == 0 or current_turn_index is None:
                current_turn_index = 1
        except Exception as e:
            # 如果获取状态失败，从数据库消息数量推断turn_index
            from app.core.logging import logging
            logging.warning(f"Failed to get MAS session status: {e}, using message count")
            message_count = (
                self.db.query(MessageEntity)
                .filter_by(session_id=session_id, account_id=account_id, deleted=0)
                .count()
            )
            # 每条消息包含user和assistant，所以turn_index = (message_count / 2) + 1
            current_turn_index = max(1, (message_count // 2) + 1)
            
            # 如果推断的turn_index >= 15，会话已结束
            if current_turn_index >= 15:
                sequence = self.__get_message_sequence(session_id)
                add_account_message = self.__add_account_message(
                    account_id, session_id, send_message_content, sequence + 1, dto.file_name
                )
                send_message_id = add_account_message.id
                self.db.add(add_account_message)
                self.db.flush()
                
                # 即使会话已结束，也要保存user消息到OA，以便MMA可以提取
                try:
                    result = loop.run_until_complete(
                        MASGatewayService.call_mas_service(
                            "oa",
                            "/receive_user_message",
                            data={
                                "patient_id": patient_id,
                                "user_input": send_message_content,
                                "turn_index": current_turn_index
                            }
                        )
                    )
                    if result.get("status") == "ok":
                        logging.info(f"✅ Saved user message to OA for patient {patient_id} (session completed, inferred): {result}")
                    else:
                        logging.warning(f"⚠️ OA returned non-ok status: {result}")
                except Exception as e:
                    import traceback
                    logging.error(f"❌ Failed to save user message to OA (session completed, inferred): {e}")
                    logging.error(f"Traceback: {traceback.format_exc()}")
                
                end_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
                sequence = self.__get_message_sequence(session_id)
                add_system_message = self.__add_system_message(
                    session_id,
                    account_id,
                    end_message,
                    "",
                    sequence + 1,
                )
                
                self.db.add(add_account_message)
                self.db.add(add_system_message)
                self.db.commit()
                self.db.flush()
                self.__refresh_session_message_count(session_id)
                self._mark_mas_session_completed(session_id, account_id)

                return {
                    "data": end_message,
                    "id": add_system_message.id,
                    "session_id": session_id,
                    "send_message_id": send_message_id,
                    "send_message_content": send_message_content,
                    "create_time": date_to_str(add_system_message.create_time),
                    "completed": True,
                }
        
        # 保存用户消息到数据库
        sequence = self.__get_message_sequence(session_id)
        add_account_message = self.__add_account_message(
            account_id, session_id, send_message_content, sequence + 1, dto.file_name
        )
        send_message_id = add_account_message.id
        self.db.add(add_account_message)
        self.db.flush()  # 立即 flush，使后续 __get_message_sequence 能取到本条，避免助手消息拿到相同 sequence 导致排序错乱
        
        # 先保存user消息到OA的goal_reviews.json，这样MMA可以从完整的对话历史中提取patient info和goals
        try:
            result = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "oa",
                    "/receive_user_message",
                    data={
                        "patient_id": patient_id,
                        "user_input": send_message_content,
                        "turn_index": current_turn_index
                    }
                )
            )
            from app.core.logging import logging
            if result.get("status") == "ok":
                logging.info(f"✅ Saved user message to OA for patient {patient_id}: {result}")
            else:
                logging.warning(f"⚠️ OA returned non-ok status: {result}")
        except Exception as e:
            from app.core.logging import logging
            import traceback
            logging.error(f"❌ Failed to save user message to OA: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            # 继续执行，不影响主流程
        
        # 发送消息到MAS服务
        message_data = {
            "patient_id": patient_id,
            "user_input": send_message_content,
            "turn_index": current_turn_index
        }
        
        # 根据turn_index判断应该发送到哪个代理
        result_data = None
        if current_turn_index <= 5:
            # SOA阶段（turn_index 1-5）
            result_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "soa",
                    "/receive_message",
                    data=message_data
                )
            )
            # 如果SOA返回错误（可能是因为turn_index >= 6），重试发送到GRA
            if result_data and result_data.get("status") == "error" and "should be sent to GRA" in result_data.get("reason", ""):
                print(f"SOA rejected turn_index {current_turn_index}, redirecting to GRA", flush=True)
                result_data = loop.run_until_complete(
                    MASGatewayService.call_mas_service(
                        "gra",
                        "/receive_message",
                        data=message_data
                    )
                )
        elif current_turn_index <= 13:
            # GRA阶段（turn_index 6-13）
            result_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "gra",
                    "/receive_message",
                    data=message_data
                )
            )
        else:
            # SCA阶段
            result_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "sca",
                    "/receive_message",
                    data=message_data
                )
            )
        
        # 检查MAS服务返回的状态，如果返回"done"，会话已结束
        if result_data and result_data.get("status") == "done":
            # 会话已结束，返回结束消息
            end_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
            sequence = self.__get_message_sequence(session_id)
            add_system_message = self.__add_system_message(
                session_id,
                account_id,
                end_message,
                "",
                sequence + 1,
            )
            
            self.db.add(add_account_message)
            self.db.add(add_system_message)
            self.db.commit()
            self.db.flush()
            self.__refresh_session_message_count(session_id)
            self._mark_mas_session_completed(session_id, account_id)

            return {
                "data": end_message,
                "id": add_system_message.id,
                "session_id": session_id,
                "send_message_id": send_message_id,
                "send_message_content": send_message_content,
                "create_time": date_to_str(add_system_message.create_time),
                "completed": True,
            }
        
        # 等待一下让MAS处理完成
        import time
        time.sleep(0.5)
        
        # 再次检查会话状态，确保会话没有在MAS处理过程中结束
        try:
            status_data = loop.run_until_complete(
                MASGatewayService.call_mas_service(
                    "oa",
                    f"/session_status/{patient_id}",
                    method="GET"
                )
            )
            updated_turn_index = status_data.get("turn_index", current_turn_index)
            session_status = status_data.get("session_status", "active")
            
            # 如果会话已结束，返回结束消息并触发MMA提取
            if session_status == "completed" or updated_turn_index >= 15:
                # 会话结束，触发MMA提取patient info和goals
                try:
                    from datetime import datetime
                    # 获取完整的对话历史
                    history_data = loop.run_until_complete(
                        MASGatewayService.call_mas_service(
                            "oa",
                            f"/conversation_history/{patient_id}",
                            method="GET"
                        )
                    )
                    
                    if history_data.get("status") == "ok" and history_data.get("chat_history"):
                        chat_history = history_data["chat_history"]
                        if len(chat_history) > 0:
                            # 将对话历史转换为笔记格式
                            formatted_lines = []
                            for msg in chat_history:
                                role = msg.get('role', 'unknown').capitalize()
                                content = msg.get('content', '').strip()
                                if content:
                                    formatted_lines.append(f"{role}: {content}")
                            note_text = "\n".join(formatted_lines)
                            
                            # 提交给MMA进行提取
                            notes_data = [{
                                "health_coach": "MAS_System",
                                "study_id": patient_id,
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "note": note_text
                            }]
                            
                            # 异步提交，不阻塞返回
                            loop.run_until_complete(
                                MASGatewayService.call_mas_service(
                                    "mma",
                                    "/extract",
                                    data=notes_data
                                )
                            )
                            from app.core.logging import logging
                            logging.info(f"✅ Triggered MMA extraction for patient {patient_id} after session completion")
                except Exception as extract_error:
                    from app.core.logging import logging
                    logging.warning(f"⚠️ Failed to trigger MMA extraction after session completion: {extract_error}")
                
                end_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
                sequence = self.__get_message_sequence(session_id)
                add_system_message = self.__add_system_message(
                    session_id,
                    account_id,
                    end_message,
                    "",
                    sequence + 1,
                )
                
                self.db.add(add_account_message)
                self.db.add(add_system_message)
                self.db.commit()
                self.db.flush()
                self.__refresh_session_message_count(session_id)
                self._mark_mas_session_completed(session_id, account_id)

                return {
                    "data": end_message,
                    "id": add_system_message.id,
                    "session_id": session_id,
                    "send_message_id": send_message_id,
                    "send_message_content": send_message_content,
                    "create_time": date_to_str(add_system_message.create_time),
                    "completed": True,
                }
        except Exception as status_error:
            from app.core.logging import logging
            logging.warning(f"Failed to check session status after MAS processing: {status_error}")
        
        # 获取最新的对话历史
        history_data = loop.run_until_complete(
            MASGatewayService.call_mas_service(
                "oa",
                f"/conversation_history/{patient_id}",
                method="GET"
            )
        )
        
        # 检查会话状态，如果已结束，返回结束消息
        if history_data.get("session_status") == "completed":
            end_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
            sequence = self.__get_message_sequence(session_id)
            add_system_message = self.__add_system_message(
                session_id,
                account_id,
                end_message,
                "",
                sequence + 1,
            )
            
            self.db.add(add_account_message)
            self.db.add(add_system_message)
            self.db.commit()
            self.db.flush()
            self.__refresh_session_message_count(session_id)
            self._mark_mas_session_completed(session_id, account_id)

            return {
                "data": end_message,
                "id": add_system_message.id,
                "session_id": session_id,
                "send_message_id": send_message_id,
                "send_message_content": send_message_content,
                "create_time": date_to_str(add_system_message.create_time),
                "completed": True,
            }
        
        # 获取最后一条助手消息
        assistant_message = "I'm processing your message..."
        if history_data.get("status") == "ok" and history_data.get("chat_history"):
            chat_history = history_data["chat_history"]
            # 找到最后一条assistant消息（排除已结束的会话）
            for msg in reversed(chat_history):
                if msg.get("role") == "assistant":
                    msg_content = msg.get("content", "")
                    # 如果消息是会话结束消息，不再重复
                    if "session has been completed" in msg_content.lower() or "see you next time" in msg_content.lower():
                        # 返回新的结束消息，而不是重复旧的
                        assistant_message = "This session has been completed. Thank you for participating in today's health coaching session. We'll see you next time!"
                    else:
                        assistant_message = msg_content
                    break
        
        # 保存助手消息到数据库
        sequence = self.__get_message_sequence(session_id)
        add_system_message = self.__add_system_message(
            session_id,
            account_id,
            assistant_message,
            "",
            sequence + 1,
        )
        
        self.db.add(add_account_message)
        self.db.add(add_system_message)
        self.db.commit()
        self.db.flush()
        self.__refresh_session_message_count(session_id)
        
        return {
            "data": assistant_message,
            "id": add_system_message.id,
            "session_id": session_id,
            "send_message_id": send_message_id,
            "send_message_content": send_message_content,
            "create_time": date_to_str(add_system_message.create_time),
            "completed": False,
        }

    def message_practice(
        self, message_id: str, dto: MessagePracticeDTO, account_id: str
    ):
        """用户发送过的消息进行练习"""
        message = self.db.query(MessageEntity).filter_by(id=message_id).first()
        if not message:
            raise Exception("Message not found")
        target_language = self.account_service.get_account_target_language(account_id)
        return word_speech_pronunciation(
            message.content, voice_file_get_path(dto.file_name), target_language
        )

    def get_word(self, dto: WordDetailDTO, account_id: str):
        """通过AI获取单词的音标与翻译"""
        # 先查询数据库中是否有数据，如果有数据就直接返回
        word = self.db.query(SysCacheEntity).filter_by(key=f"word_{dto.word}").first()
        if word:
            return json.loads(word.value)
        invoke_result = chat_ai.invoke_word_detail(WordDetailParams(word=dto.word))
        result = invoke_result.__dict__
        result["original"] = dto.word
        # result 转换成字符串进行保存
        sys_cache = SysCacheEntity(key=f"word_{dto.word}", value=json.dumps(result))
        self.db.add(sys_cache)
        self.db.commit()
        return result

    def grammar_analysis(self, dto: GrammarDTO, account_id: str):
        message = self.db.query(MessageEntity).filter_by(id=dto.message_id).first()
        if not message:
            raise UserAccessDeniedException("message不存在")
        # 检查AccountGrammarEntity是否已经存在数据，如果存在就直接返回已经保存的数据
        message_grammar = (
            self.db.query(MessageGrammarEntity)
            .filter_by(
                message_id=dto.message_id, file_name=message.file_name, type="GRAMMAR"
            )
            .first()
        )
        if message_grammar:
            return json.loads(message_grammar.result)

        content = message.content
        target_language = self.account_service.get_account_target_language(account_id)
        result = chat_ai.invoke_grammar_analysis(
            GrammarAnalysisParams(language=target_language, content=content)
        ).__dict__
        result["original"] = content
        # result是json格式的字符串，把result 解析成json返回
        # 结果以字符串方式保存到数据库中
        message_grammar = MessageGrammarEntity(
            account_id=account_id,
            session_id=message.session_id,
            message_id=dto.message_id,
            file_name=message.file_name,
            type="GRAMMAR",
            result=json.dumps(result),
        )
        self.db.add(message_grammar)
        self.db.commit()
        return result

    def word_practice(self, dto: WordPracticeDTO, account_id: str):
        """单词发音练习"""
        target_language = self.account_service.get_account_target_language(account_id)
        return word_speech_pronunciation(
            dto.word, voice_file_get_path(dto.file_name), language=target_language
        )

    def pronunciation(self, dto: PronunciationDTO, account_id: str):
        """发单评估"""
        # 先根据message_id查询出message
        message = self.db.query(MessageEntity).filter_by(id=dto.message_id).first()
        if not message:
            raise UserAccessDeniedException("message不存在")
        file_name = message.file_name
        if not file_name:
            raise UserAccessDeniedException("message中没有语音文件")

        # 检查AccountGrammarEntity是否已经存在数据，如果存在就直接返回已经保存的数据
        grammar = (
            self.db.query(MessageGrammarEntity)
            .filter_by(
                message_id=dto.message_id,
                file_name=message.file_name,
                type="PRONUNCIATION",
            )
            .first()
        )
        if grammar:
            return json.loads(grammar.result)

        file_full_path = voice_file_get_path(file_name)
        # 检查文件是否存在
        if not os.path.exists(file_full_path):
            raise UserAccessDeniedException("语音文件不存在")
        target_language = self.account_service.get_account_target_language(account_id)
        # 进行评分
        try:
            session = (
                self.db.query(MessageSessionEntity)
                .filter_by(id=message.session_id)
                .first()
            )
            pronunciation_result = word_speech_pronunciation(
                message.content, file_full_path, language=target_language
            )
            logging.info("end")
        except Exception as e:
            # 输出错误信息
            logging.exception(
                f"file_full_path:{file_full_path}\n content:{message.content}", e
            )
            raise UserAccessDeniedException("语音评估失败")
        # 结果以字符串方式保存到数据库中
        message_grammar = MessageGrammarEntity(
            account_id=account_id,
            session_id=message.session_id,
            message_id=dto.message_id,
            file_name=message.file_name,
            type="PRONUNCIATION",
            result=json.dumps(pronunciation_result),
        )
        self.db.add(message_grammar)
        self.db.commit()
        return pronunciation_result

    def message_speech_content(self, dto: TransformContentSpeechDTO, account_id: str):
        """如果file表中已经存在文件的保存，则直接返回，如果不存在，生成一份并保存"""
        # 根据convert_language与speech_role_name，speech_rate,speech_style来生成唯一标识,用于生成缓存的key
        # 获取用户语言
        account_settings = (
            self.db.query(AccountSettingsEntity)
            .filter_by(account_id=account_id)
            .first()
        )
        target_language = account_settings.target_language
        set_speech_role_name = None
        set_speech_role_style = ""
        if dto.speech_role_name:
            set_speech_role_name = dto.speech_role_name
            if dto.speech_role_style:
                set_speech_role_style = dto.speech_role_style
        elif account_settings.speech_role_name:
            set_speech_role_name = account_settings.speech_role_name

        set_speech_rate = "1.0"
        if dto.speech_rate:
            set_speech_rate = dto.speech_rate
        elif account_settings.speech_role_speed:
            set_speech_rate = account_settings.speech_role_speed

        content_md5 = hashlib.md5(dto.content.encode("utf-8")).hexdigest()
        key = f"content_{set_speech_role_name}_{set_speech_role_style}_{set_speech_rate}_{content_md5}"
        file_module = "SPEECH_CONTENT_VOICE"
        # 对key进行md5加密
        file_detail = (
            self.db.query(FileDetail)
            .filter_by(module=file_module, module_id=key, deleted=0)
            .first()
        )
        if file_detail:
            # 检查文件是否存在，只有文件存在情况下才进行返回
            if os.path.exists(voice_file_get_path(file_detail.file_name)):
                return {"file": file_detail.file_name}
            else:
                # 如果文件不存在，就删除数据库中的记录，重新生成
                file_detail.deleted = 1
                self.db.commit()

        # 调用speech组件，将speech_content转换成语音文件
        filename = f"{key}.wav"
        full_file_name = voice_file_get_path(filename)

        if set_speech_rate != "1.0" or set_speech_role_style:
            speech_by_ssml(
                dto.content,
                full_file_name,
                voice_name=set_speech_role_name,
                speech_rate=set_speech_rate,
                feel=set_speech_role_style,
                targetLang=target_language,
            )
        else:
            speech_default(
                dto.content, full_file_name, target_language, set_speech_role_name
            )

        file_detail = FileDetail(
            id=short_uuid(),
            file_path=filename,
            module=file_module,
            file_name=filename,
            module_id=key,
            file_ext="wav",
            created_by=account_id,
        )
        self.db.add(file_detail)
        self.db.commit()
        self.db.flush()
        return {"file": file_detail.file_name}

    def message_speech(self, message_id: str, account_id: str):
        """文字转语音"""
        # 如果没有，就生成一个
        message = self.db.query(MessageEntity).filter_by(id=message_id).first()

        # 获取用户的语音配置
        account_settings = (
            self.db.query(AccountSettingsEntity)
            .filter_by(account_id=account_id)
            .first()
        )
        target_language = account_settings.target_language
        voice_name = account_settings.speech_role_name
        speech_speed = account_settings.playing_voice_speed
        filename = f"message_{message.id}_{voice_name}_{speech_speed}.wav"
        full_file_name = voice_file_get_path(filename)
        voice_role_style = ""
        if message.style:
            voice_role_style = message.style
        speech_by_ssml(
            message.content,
            full_file_name,
            voice_name=voice_name,
            speech_rate=speech_speed,
            feel=voice_role_style,
            targetLang=target_language,
        )

        file_detail = FileDetail(
            id=short_uuid(),
            file_path=filename,
            module="SPEECH_VOICE",
            file_name=filename,
            module_id=message_id,
            file_ext="wav",
            created_by=account_id,
        )
        self.db.add(file_detail)
        message.file_name = filename
        self.db.commit()
        return {"file": file_detail.file_name}

    def create_session(self, account_id: str, session_type: str = "CHAT"):
        """
        为用户创建新的session，并且设置成默认的session
        
        Args:
            account_id: 用户ID
            session_type: 会话类型，可选值：CHAT（默认）、TOPIC、MAS
        """
        session = MessageSessionEntity(
            id=f"session_{short_uuid()}", 
            account_id=account_id, 
            type=session_type,
            is_default=1
        )
        self.db.add(session)
        self.db.commit()
        return self.__convert_session_model(session)
    
    def create_mas_session(self, account_id: str):
        """
        创建MAS健康教练会话
        
        创建新会话时，会重置OA中该患者的会话计数（turn_index和chat_history）
        """
        # 创建数据库会话
        session = self.create_session(account_id, session_type="MAS")
        
        # 重置OA中的会话计数
        try:
            from app.services.mas.patient_mapping_service import PatientMappingService
            from app.config import Config
            import requests
            
            mapping_service = PatientMappingService(self.db)
            patient_id = mapping_service.get_or_create_patient_id(account_id)
            
            # 使用同步请求调用OA的重置接口（避免事件循环冲突）
            oa_url = Config.MAS_OA_URL
            reset_url = f"{oa_url}/reset_session/{patient_id}"
            
            try:
                response = requests.post(reset_url, json={}, timeout=5)
                if response.status_code == 200:
                    reset_result = response.json()
                    from app.core.logging import logging
                    if reset_result.get("status") == "ok":
                        logging.info(f"✅ Reset OA session for patient {patient_id} when creating new MAS session: turn_index={reset_result.get('turn_index', 0)}")
                    else:
                        logging.error(f"❌ Failed to reset OA session for patient {patient_id}: {reset_result}")
                else:
                    from app.core.logging import logging
                    logging.error(f"❌ Failed to reset OA session: HTTP {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as req_error:
                from app.core.logging import logging
                logging.error(f"❌ Failed to reset OA session (network error): {req_error}")
        except Exception as e:
            from app.core.logging import logging
            import traceback
            logging.error(f"❌ Failed to reset OA session when creating MAS session: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            # 即使重置失败，也返回创建的session，不影响用户体验
        
        return session
    
    def get_or_create_mas_session(self, account_id: str):
        """
        获取或创建MAS健康教练会话
        
        优先返回用户最新的MAS会话，如果没有则创建一个新的
        """
        # 查找用户最新的MAS会话
        session = (
            self.db.query(MessageSessionEntity)
            .filter_by(
                account_id=account_id,
                type="MAS",
            )
            .order_by(MessageSessionEntity.create_time.desc())
            .first()
        )
        if not session:
            # 如果没有MAS会话，创建一个新的（会触发重置）
            return self.create_mas_session(account_id)

        # 不再在此处根据 OA「预约已触发」强制新建会话：该逻辑会导致用户每次从首页点「Chat with Coach」
        # 反复 get-or-create 时都命中「会话早于 trigger」而新建空会话，进而每次 initData 都拉 greeting。
        # 到点后的新会话由 App 轮询 / New Session / 用户主动「新建会话」完成。

        return self.__convert_session_model(session)

    def get_mas_sessions_list(self, account_id: str, limit: int = 50):
        """
        获取用户所有 MAS 会话列表，按创建时间倒序（最新的在前）
        用于历史对话侧栏展示
        """
        sessions = (
            self.db.query(MessageSessionEntity)
            .filter_by(account_id=account_id, type="MAS")
            .order_by(MessageSessionEntity.create_time.desc())
            .limit(limit)
            .all()
        )
        result = []
        has_updated_count = False
        for s in sessions:
            actual_count = (
                self.db.query(MessageEntity)
                .filter_by(session_id=s.id, account_id=account_id, deleted=0)
                .count()
            )
            if s.message_count != actual_count:
                s.message_count = actual_count
                has_updated_count = True
            result.append(self.__convert_session_model(s))

        if has_updated_count:
            self.db.commit()

        return result

    def _mark_mas_session_completed(self, session_id: str, account_id: str) -> None:
        row = (
            self.db.query(MessageSessionEntity)
            .filter_by(id=session_id, account_id=account_id, type="MAS")
            .first()
        )
        if row:
            row.completed = 1
            self.db.commit()

    def _hard_delete_mas_session_data(self, session_id: str, account_id: str) -> None:
        msgs = (
            self.db.query(MessageEntity)
            .filter_by(session_id=session_id, account_id=account_id)
            .all()
        )
        mids = [m.id for m in msgs]
        if mids:
            self.db.query(FileDetail).filter(FileDetail.module_id.in_(mids)).delete(
                synchronize_session=False
            )
        self.db.query(MessageGrammarEntity).filter_by(
            session_id=session_id, account_id=account_id
        ).delete(synchronize_session=False)
        self.db.query(MessageTranslateEntity).filter_by(
            session_id=session_id, account_id=account_id
        ).delete(synchronize_session=False)
        self.db.query(MessageEntity).filter_by(
            session_id=session_id, account_id=account_id
        ).delete(synchronize_session=False)
        self.db.query(MessageSessionEntity).filter_by(
            id=session_id, account_id=account_id
        ).delete(synchronize_session=False)
        self.db.commit()

    def delete_mas_sessions_bulk(self, account_id: str, session_ids: list) -> dict:
        deleted = []
        failed = []
        for sid in session_ids or []:
            if not sid:
                continue
            s = (
                self.db.query(MessageSessionEntity)
                .filter_by(id=sid, account_id=account_id)
                .first()
            )
            if not s:
                failed.append({"id": sid, "reason": "not_found"})
                continue
            if s.type != "MAS":
                failed.append({"id": sid, "reason": "not_mas"})
                continue
            if (s.completed or 0) == 1:
                failed.append({"id": sid, "reason": "completed"})
                continue
            try:
                self._hard_delete_mas_session_data(sid, account_id)
                deleted.append(sid)
            except Exception as e:
                from app.core.logging import logging

                logging.exception("delete_mas_sessions_bulk failed for %s", sid)
                failed.append({"id": sid, "reason": str(e)})
        return {"deleted": deleted, "failed": failed}

    def get_session_messages(
        self, session_id: str, account_id: str, page: int, page_size: int
    ):
        query = (
            self.db.query(MessageEntity)
            .filter_by(session_id=session_id, account_id=account_id, deleted=0)
            .filter(
                MessageEntity.type.in_(
                    [MessageType.ACCOUNT.value, MessageType.SYSTEM.value]
                )
            )
        )
        # 以 sequence 为主排序（严格按插入顺序），create_time 为次排序，保证问答顺序正确
        messages = (
            query.order_by(MessageEntity.sequence.asc(), MessageEntity.create_time.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        # 获取总数
        total = query.count()
        result = []
        for message in messages:
            result.append(self.initMessageResult(message))

        # 如果是我的消息，则检查是否进行过语音分析，如果进行过就加载分析结果
        self.initOwnerMessagePronunciation(result)
        return {"total": total, "list": result}

    def prompt_sentence(self, dto: PromptDTO, account_id: str):
        """提示用户下一句话"""
        # 查询出session中最后5条消息
        messageEntities = (
            self.db.query(MessageEntity)
            .filter_by(session_id=dto.session_id)
            .order_by(MessageEntity.create_time.desc())
            .limit(5)
            .all()
        )
        messages = []
        for message in messageEntities:
            messages.append(self.initMessageResult(message))

        target_language = self.account_service.get_account_target_language(account_id)
        return chat_ai.invoke_prompt_sentence(
            PromptSentenceParams(language=target_language, messages=messages)
        )

    def delete_all_session_messages(self, session_id: str, account_id: str):
        """把所有的消息都调整为deleted=1"""
        messages = (
            self.db.query(MessageEntity)
            .filter_by(session_id=session_id, account_id=account_id, deleted=0)
            .all()
        )
        for message in messages:
            message.deleted = 1
        self.db.commit()
        return True

    def transform_text(self, session_id: str, dto: VoiceTranslateDTO, account_id: str):
        """语音解析成文字（使用 Whisper）"""
        return _voice_to_text(voice_file_get_path(dto.file_name))

    def delete_latest_session_messages(self, session_id: str, account_id: str):
        """查出最近的一条type为ACCOUNT的数据，并且把create_time之后的数据全部调整为deleted=1，删除成功后需要返回所有删除成功的message的id"""
        message = (
            self.db.query(MessageEntity)
            .filter_by(
                session_id=session_id,
                account_id=account_id,
                type=MessageType.ACCOUNT.value,
                deleted=0,
            )
            .order_by(MessageEntity.create_time.desc())
            .first()
        )
        if message:
            # 获取所有需要删除的数据
            messages = (
                self.db.query(MessageEntity)
                .filter_by(session_id=session_id, deleted=0)
                .filter(MessageEntity.create_time >= message.create_time)
                .all()
            )
            for message in messages:
                message.deleted = 1
            self.db.commit()
            return [message.id for message in messages]
        return []

    def initOwnerMessagePronunciation(self, result):
        # 过滤出所有role为USER的id列表，然后根据id列表获取所有的message_pronunciation，再组装到item中，不存在则组装None
        user_message_ids = [item["id"] for item in result if item["role"] == "USER"]
        message_pronunciations = (
            self.db.query(MessageGrammarEntity)
            .filter(
                MessageGrammarEntity.message_id.in_(user_message_ids),
                MessageGrammarEntity.type == "PRONUNCIATION",
            )
            .all()
        )
        for item in result:
            if item["role"] == "USER":
                item["pronunciation"] = None
                for message_pronunciation in message_pronunciations:
                    if message_pronunciation.message_id == item["id"]:
                        item["pronunciation"] = json.loads(message_pronunciation.result)
                        break

    def translate_source_language(self, dto: TranslateTextDTO, account_id: str):
        """翻译成源语言"""
        source_language = self.account_service.get_account_source_language(account_id)
        result = self.translate_language(dto.text, source_language)
        return result

    def translate_setting_language(self, dto: TranslateTextDTO, account_id: str):
        """翻译成目标语言，也就是用户学习的语言"""
        # 获取用户配置language
        account_settings = (
            self.db.query(AccountSettingsEntity)
            .filter_by(account_id=account_id)
            .first()
        )
        result = self.translate_language(dto.text, account_settings.target_language)
        return result

    def translate_language(self, content: str, language: str):
        """翻译成参数中配置的语言"""
        result = chat_ai.invoke_translate(
            TranslateParams(target_language=language, content=content)
        )
        return result

    def translate_message(self, message_id: str, account_id: str):
        # 检查是否已经生成了对应翻译，生成的话直接返回
        message_translate = (
            self.db.query(MessageTranslateEntity)
            .filter_by(message_id=message_id)
            .first()
        )
        if message_translate:
            return message_translate.target_text

        message = self.db.query(MessageEntity).filter_by(id=message_id).first()
        content = message.content
        source_language = self.account_service.get_account_source_language(account_id)
        target_language = self.account_service.get_account_target_language(account_id)
        result = self.translate_source_language(
            TranslateTextDTO(text=content), account_id
        )

        account_translate = MessageTranslateEntity(
            account_id=account_id,
            session_id=message.session_id,
            message_id=message_id,
            target_language=target_language,
            source_language=source_language,
            source_text=content,
            target_text=result,
        )
        self.db.add(account_translate)
        self.db.commit()
        return result

    def add_mas_state_event_message(
        self, account_id: str, content: str, style: str
    ) -> dict:
        """写入健康顾问状态消息（不计入代理轮次；前端用 style=STATE_EVENT:* 区分展示）。"""
        session = (
            self.db.query(MessageSessionEntity)
            .filter_by(account_id=account_id, type="MAS")
            .order_by(MessageSessionEntity.create_time.desc())
            .first()
        )
        if not session:
            created = self.create_session(account_id, session_type="MAS")
            session_id = created["id"]
        else:
            session_id = session.id
        sequence = self.__get_message_sequence(session_id)
        add_message = self.__add_system_message(
            session_id, account_id, content, style, sequence + 1
        )
        self.db.add(add_message)
        self.db.commit()
        self.db.flush()
        self.__refresh_session_message_count(session_id)
        return self.initMessageResult(add_message)

    def initMessageResult(self, message: MessageEntity):
        st = message.style or ""
        message_kind = "state_event" if st.startswith("STATE_EVENT:") else "conversation"
        return {
            "role": "ASSISTANT" if message.type == MessageType.SYSTEM.value else "USER",
            "content": message.content,
            "file_name": message.file_name,
            "id": message.id,
            "create_time": date_to_str(message.create_time),
            "session_id": message.session_id,
            "style": st,
            "message_kind": message_kind,
        }

    def __convert_session_model(self, session: MessageSessionEntity):
        return {
            "id": session.id,
            "type": session.type,
            "message_count": session.message_count,
            "create_time": date_to_str(session.create_time),
            "friendly_time": friendly_time(date_to_str(session.create_time)),
            "completed": 1 if (session.completed or 0) == 1 else 0,
        }

    def __add_account_message(
        self, account_id: str, session_id: str, content: str, sequence: int, file_name: str = None
    ):
        """添加用户消息"""
        message = MessageEntity(
            id=short_uuid(),
            account_id=account_id,
            sender=account_id,
            session_id=session_id,
            receiver=MESSAGE_SYSTEM,
            type=MessageType.ACCOUNT.value,
            content=content,
            file_name=file_name,
            length=len(content),
            sequence=sequence,
        )
        return message

    def __add_system_message(
        self, session_id, account_id: str, content: str, style: str, sequence: int
    ) -> MessageEntity:
        """添加系统消息"""
        add_message = MessageEntity(
            id=short_uuid(),
            account_id=account_id,
            sender=MESSAGE_SYSTEM,
            session_id=session_id,
            receiver=account_id,
            type=MessageType.SYSTEM.value,
            content=content,
            style=style,
            length=len(content),
            sequence=sequence,
        )
        return add_message

    def __refresh_session_message_count(self, session_id: str):
        """刷新session的消息数量, 需要排除deleted为1的数据"""
        count = (
            self.db.query(MessageEntity)
            .filter(MessageEntity.session_id == session_id, MessageEntity.deleted == 0)
            .count()
        )
        self.db.query(MessageSessionEntity).filter(
            MessageSessionEntity.id == session_id
        ).update({"message_count": count})
        self.db.commit()
        self.db.flush()

    def __get_and_check_session(
        self, session_id: str, account_id: str
    ) -> MessageSessionEntity:
        """检查会话是否存在"""
        session = (
            self.db.query(MessageSessionEntity)
            .filter_by(id=session_id, account_id=account_id)
            .first()
        )
        if not session:
            raise Exception("Session not found")
        return session

    def __check_has_messages(self, session_id: str, account_id: str):
        """检查会话下是否已经有了消息"""
        messages = (
            self.db.query(MessageEntity)
            .filter_by(session_id=session_id, account_id=account_id, deleted=0)
            .order_by(MessageEntity.create_time.desc())
            .slice(0, 1)
            .all()
        )
        if len(messages) == 1:
            raise Exception("Session has messages")
        
    def __get_message_sequence(self, session_id: str):
        """获取当前会话内最大的 sequence，保证同一会话内消息严格按插入顺序排列"""
        sequence = (
            self.db.query(MessageEntity)
            .filter_by(session_id=session_id, deleted=0)
            .order_by(MessageEntity.sequence.desc())
            .first()
        )
        if sequence:
            return sequence.sequence
        return 0    
