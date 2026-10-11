/**
 * Model-output JSON extraction.
 *
 * Port of the MiroFish-derived logic in engine/desnworld/llm_client.py:
 * - strips reasoning wrappers and Markdown JSON fences;
 * - accepts a single complete JSON object even when trailing prose follows;
 * - never repairs or invents truncated JSON;
 * - rejects multiple JSON values and non-object top-level values.
 */
import { MalformedResponseError } from './errors.js'

export function cleanChatText(content) {
  let cleaned = String(content || '')
  const THINK_OPEN = '<think>'
  const THINK_CLOSE = '</think>'
  cleaned = cleaned.replace(
    new RegExp(THINK_OPEN + '[\\s\\S]*?' + THINK_CLOSE, 'g'),
    ''
  )
  cleaned = cleaned.replace(/^\uFEFF/, '')
  cleaned = cleaned.replace(/^```(?:json)?\s*\n?/i, '')
  cleaned = cleaned.replace(/\n?```\s*$/, '')
  return cleaned.trim()
}

/**
 * Walk from the first object opener and return [value, endIndex] when a
 * single complete JSON object can be decoded from the start position.
 */
function rawDecodeObject(text, start) {
  if (text[start] !== '{') return null
  let depth = 0
  let inString = false
  let escaped = false
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i]
    if (inString) {
      if (escaped) escaped = false
      else if (ch === '\\') escaped = true
      else if (ch === '"') inString = false
      continue
    }
    if (ch === '"') inString = true
    else if (ch === '{') depth += 1
    else if (ch === '}') {
      depth -= 1
      if (depth === 0) {
        const slice = text.slice(start, i + 1)
        try {
          return [JSON.parse(slice), i + 1]
        } catch {
          return null
        }
      }
    }
  }
  return null
}

function containsAdditionalJsonContainer(text) {
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] !== '{' && text[i] !== '[') continue
    if (text[i] === '{') {
      if (rawDecodeObject(text, i)) return true
    } else {
      // arrays: try JSON.parse on progressively balanced slices
      let depth = 0
      let inString = false
      let escaped = false
      for (let j = i; j < text.length; j += 1) {
        const ch = text[j]
        if (inString) {
          if (escaped) escaped = false
          else if (ch === '\\') escaped = true
          else if (ch === '"') inString = false
          continue
        }
        if (ch === '"') inString = true
        else if (ch === '[') depth += 1
        else if (ch === ']') {
          depth -= 1
          if (depth === 0) {
            try {
              JSON.parse(text.slice(i, j + 1))
              return true
            } catch {
              break
            }
          }
        }
      }
    }
  }
  return false
}

/**
 * Parse a chat completion content string into a plain JSON object.
 * Mirrors LLMClient._parse_json_response semantics.
 */
export function parseJsonContent(content, finishReason = 'stop') {
  if (finishReason === 'length') {
    throw new MalformedResponseError(
      'The AI model output was truncated at the token limit.',
      { hint: 'Raise max output tokens on the provider side or use a model with a larger limit.' }
    )
  }
  if (finishReason && finishReason !== 'stop' && finishReason !== 'end_turn') {
    throw new MalformedResponseError(
      `The AI model stopped generating unexpectedly (${finishReason}).`
    )
  }
  const cleaned = cleanChatText(content)
  if (!cleaned) {
    throw new MalformedResponseError('The AI model returned empty content.')
  }
  try {
    const value = JSON.parse(cleaned)
    if (Array.isArray(value) || typeof value !== 'object' || value === null) {
      throw new MalformedResponseError('The AI model response must be a top-level JSON object.')
    }
    return value
  } catch (err) {
    if (err instanceof MalformedResponseError) throw err
    // Tolerate trailing prose after one complete object; never repair truncation.
    for (let i = 0; i < cleaned.length; i += 1) {
      if (cleaned[i] !== '{') continue
      const decoded = rawDecodeObject(cleaned, i)
      if (!decoded) continue
      const [value, end] = decoded
      const trailing = cleaned.slice(end).trim()
      if (trailing && containsAdditionalJsonContainer(trailing)) {
        throw new MalformedResponseError('The AI model returned multiple JSON values.')
      }
      if (Array.isArray(value) || typeof value !== 'object' || value === null) {
        throw new MalformedResponseError('The AI model response must be a top-level JSON object.')
      }
      return value
    }
    throw new MalformedResponseError('The AI model returned invalid JSON.')
  }
}
