/**
 * EP06 demo bundle — the Host half.
 *
 * One package, two model/human facing entry points:
 *   ctx.tools.register()    → the model can call `greet`
 *   ctx.commands.register() → a human can type `/greet`
 *
 * The Client half (client.js) adds the third entry point: a dock entry.
 */

export const inject = ['tools', 'commands']

export function apply(ctx) {
  // 1) 面向模型：一个工具。参数与返回值都是 JSON Schema。
  ctx.tools.register({
    name: 'greet',
    description: 'Say hello to one name. Demo tool registered by @local/greet.',
    parameters: {
      type: 'object',
      properties: { name: { type: 'string', description: 'Who to greet' } },
      required: ['name'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return `hello, ${args.name}`
    },
  })

  // 2) 面向人：一条斜杠命令。handler 直接返回 UI 要显示的结果。
  ctx.commands.register({
    definitionId: '@local/greet',
    name: 'greet',
    description: 'Say hello from the EP06 demo bundle',
    input: { hint: '<name>', attachments: false },
    handler: invocation => ({
      kind: 'success',
      text: `hello, ${invocation.rawInput.trim() || 'world'}`,
    }),
  })
}
