import { reactive } from 'vue'

export const toastStore = reactive({
  items: [],   // storico ultimi 100

  push(toast) {
    this.items.unshift(toast)
    if (this.items.length > 100) {
      this.items.pop()
    }
  }
})