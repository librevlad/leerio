import type { Directive } from 'vue'

const HANDLER_KEY = '__rippleHandler'

interface RippleElement extends HTMLElement {
  [HANDLER_KEY]?: (e: PointerEvent) => void
}

const ripple: Directive<RippleElement> = {
  mounted(el) {
    el.style.position = el.style.position || 'relative'
    el.style.overflow = 'hidden'

    const handler = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const size = Math.max(rect.width, rect.height) * 2

      const span = document.createElement('span')
      span.style.cssText = `
        position: absolute;
        left: ${x - size / 2}px;
        top: ${y - size / 2}px;
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,138,0,0.18) 0%, transparent 60%);
        transform: scale(0);
        pointer-events: none;
        animation: v-ripple 0.45s cubic-bezier(0.2, 0, 0, 1) forwards;
      `
      el.appendChild(span)
      span.addEventListener('animationend', () => span.remove())
    }

    el[HANDLER_KEY] = handler
    el.addEventListener('pointerdown', handler, { passive: true })
  },
  unmounted(el) {
    if (el[HANDLER_KEY]) {
      el.removeEventListener('pointerdown', el[HANDLER_KEY])
    }
  },
}

export default ripple
