import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initTelegram } from './telegram'
import { postAppEvent } from './analytics'
import './style.css'

initTelegram()

const app = createApp(App)

app.config.errorHandler = (err: any, _instance, info) => {
  console.error('[Vue Error]', err)
  postAppEvent('vue_error', {
    message: err?.message || String(err),
    stack: err?.stack,
    info: String(info),
  })
}

window.addEventListener('error', (event) => {
  console.error('[Window Error]', event.error)
  postAppEvent('window_error', {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
    stack: event.error?.stack,
  })
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
  postAppEvent('unhandled_rejection', {
    message: event.reason?.message || String(event.reason),
    stack: event.reason?.stack,
  })
})

app.use(router).mount('#app')
