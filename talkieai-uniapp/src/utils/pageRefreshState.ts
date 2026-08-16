let homeRefreshNeeded = false;

export const markHomeRefreshNeeded = () => {
  homeRefreshNeeded = true;
};

export const consumeHomeRefreshNeeded = () => {
  const needed = homeRefreshNeeded;
  homeRefreshNeeded = false;
  return needed;
};

export const resetPageRefreshState = () => {
  homeRefreshNeeded = false;
};
