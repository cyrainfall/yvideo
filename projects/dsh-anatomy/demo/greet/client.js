/**
 * EP06 demo bundle — the Client half.
 *
 * Loading a bundle only registers a factory; nothing renders until the slot
 * asks for it. The component is plain React from the browser module table.
 */
window.__ModuleLoader__.load({
  id: '@local/greet',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    function GreetDock() {
      return h(
        'div',
        { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, opacity: 0.85 } },
        h('span', {
          style: { width: 7, height: 7, borderRadius: '50%', background: '#4D6BFE', display: 'block' },
        }),
        h('span', null, 'greet'),
      )
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('conversation.composer.dock', () =>
          ctx.slots.register(
            { name: 'conversation.composer.dock', id: 'greet', order: 50 },
            GreetDock,
          ),
        )
      },
    }
  },
})
