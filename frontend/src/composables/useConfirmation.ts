export function useConfirmation() {
  const confirm = (message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      if (window.confirm(message)) {
        resolve(true)
      } else {
        resolve(false)
      }
    })
  }

  return {
    confirm,
  }
}
