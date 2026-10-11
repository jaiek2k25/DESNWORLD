import { describe, it, expect } from 'vitest'
import { parseJsonContent, cleanChatText } from '../src/engine/json.js'
import { MalformedResponseError } from '../src/engine/errors.js'

describe('cleanChatText', () => {
  it('strips markdown JSON fences', () => {
    expect(cleanChatText('```json\n{"a": 1}\n```')).toBe('{"a": 1}')
  })

  it('strips BOM', () => {
    expect(cleanChatText('\uFEFF{"a": 1}')).toBe('{"a": 1}')
  })
})

describe('parseJsonContent', () => {
  it('parses a plain object', () => {
    expect(parseJsonContent('{"a": 1}')).toEqual({ a: 1 })
  })

  it('tolerates trailing prose', () => {
    expect(parseJsonContent('{"a": 1}\nI hope this helps!')).toEqual({ a: 1 })
  })

  it('rejects multiple JSON values', () => {
    expect(() => parseJsonContent('{"a": 1} {"b": 2}')).toThrow(MalformedResponseError)
  })

  it('rejects truncated JSON without repairing it', () => {
    expect(() => parseJsonContent('{"a": 1, "b": {"nested": tru')).toThrow(MalformedResponseError)
  })

  it('rejects empty content', () => {
    expect(() => parseJsonContent('   ')).toThrow(MalformedResponseError)
  })

  it('rejects length-truncated output', () => {
    expect(() => parseJsonContent('{"a": 1}', 'length')).toThrow(MalformedResponseError)
  })

  it('rejects top-level arrays', () => {
    expect(() => parseJsonContent('[1, 2, 3]')).toThrow(MalformedResponseError)
  })

  it('rejects unexpected finish reasons', () => {
    expect(() => parseJsonContent('{"a": 1}', 'tool_calls')).toThrow(MalformedResponseError)
  })
})
