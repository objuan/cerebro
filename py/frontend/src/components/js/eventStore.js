import { reactive } from 'vue'

export const eventStore = reactive({
  items: [],   // storico ultimi 200

  push(evt) {
    this.items.unshift(evt)
    if (this.items.length > 200) {
      this.items.pop()
    }
  }
})