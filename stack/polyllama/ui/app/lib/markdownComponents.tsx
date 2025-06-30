'use client'

const extractText = (node: React.ReactNode): string => {
  if (typeof node === 'string') return node
  if (!node) return ''
  if (typeof node === 'object' && 'props' in node) {
    const nodeWithProps = node as { props: { children?: React.ReactNode } }
    if (nodeWithProps.props?.children) {
      if (Array.isArray(nodeWithProps.props.children)) {
        return nodeWithProps.props.children.map(extractText).join('')
      }
      return extractText(nodeWithProps.props.children)
    }
  }
  return ''
}

interface MarkdownComponentsProps {
  messageIndex?: number
  timestamp?: string
  copiedCode: { [key: string]: boolean }
  setCopiedCode: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>
}

export const createMarkdownComponents = ({ 
  messageIndex = 0, 
  timestamp = '',
  copiedCode,
  setCopiedCode
}: MarkdownComponentsProps) => {
  const handleCodeCopy = (key: string, children: React.ReactNode) => {
    const codeText = extractText(children)
    navigator.clipboard.writeText(codeText)
    setCopiedCode({ ...copiedCode, [key]: true })
    setTimeout(() => setCopiedCode({ ...copiedCode, [key]: false }), 2000)
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markdownComponents: any = {
    pre: ({ children }: { children: React.ReactNode }) => {
      const key = `pre-${messageIndex}-${timestamp}`
      const copied = copiedCode[key] || false

      return (
        <div className="relative group my-2">
          <button
            onClick={() => handleCodeCopy(key, children)}
            className="absolute top-2 right-2 flex items-center justify-center w-6 h-6 rounded bg-gray-800 hover:bg-gray-700 opacity-0 group-hover:opacity-100 transition-all"
            title="Copy code"
          >
            {copied ? (
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>
          <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto border border-gray-700">
            {children}
          </pre>
        </div>
      )
    },
    code: ({ className, children, ...props }: { className?: string; children: React.ReactNode }) => {
      const match = /language-(\w+)/.exec(className || '')
      const isInline = !match
      return isInline ? (
        <code className="bg-gray-100 text-gray-800 rounded px-1.5 py-0.5 text-sm font-mono" {...props}>
          {children}
        </code>
      ) : (
        <code className="text-gray-100 text-sm font-mono block" {...props}>
          {children}
        </code>
      )
    },
    a: ({ href, children }: { href?: string; children: React.ReactNode }) => (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline">
        {children}
      </a>
    ),
    ul: ({ children }: { children: React.ReactNode }) => (
      <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>
    ),
    ol: ({ children }: { children: React.ReactNode }) => (
      <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>
    ),
    blockquote: ({ children }: { children: React.ReactNode }) => (
      <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2 text-gray-700">{children}</blockquote>
    ),
    h1: ({ children }: { children: React.ReactNode }) => (
      <h1 className="text-2xl font-bold mt-4 mb-2">{children}</h1>
    ),
    h2: ({ children }: { children: React.ReactNode }) => (
      <h2 className="text-xl font-bold mt-3 mb-2">{children}</h2>
    ),
    h3: ({ children }: { children: React.ReactNode }) => (
      <h3 className="text-lg font-bold mt-2 mb-1">{children}</h3>
    ),
    p: ({ children }: { children: React.ReactNode }) => (
      <p className="my-2">{children}</p>
    ),
    table: ({ children }: { children: React.ReactNode }) => (
      <div className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse border border-gray-300">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: { children: React.ReactNode }) => (
      <th className="border border-gray-300 px-4 py-2 bg-gray-100 font-semibold text-left">
        {children}
      </th>
    ),
    td: ({ children }: { children: React.ReactNode }) => (
      <td className="border border-gray-300 px-4 py-2">
        {children}
      </td>
    ),
  }

  return markdownComponents
}