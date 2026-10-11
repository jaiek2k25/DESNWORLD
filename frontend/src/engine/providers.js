/**
 * AI providers for the in-browser DESNWORLD engine.
 *
 * BrowserLLMProvider calls any OpenAI-compatible Chat Completions endpoint
 * directly from the user's browser with the user's OWN runtime credentials —
 * no API keys are embedded in this codebase. The key never leaves the browser
 * except in the Authorization header sent to the endpoint the user configured.
 *
 * Compatibility notes (mirrored from engine/desnworld/openai_chat_compat.py):
 * - GPT-5 family models: temperature omitted, `max_completion_tokens` used.
 * - `response_format: {type: 'json_object'}` is negotiated once; an explicit
 *   provider rejection downgrades to prompt-only JSON guidance.
 * - 429/5xx and network failures retry with exponential backoff.
 */
import {
  MalformedResponseError,
  MissingCredentialsError,
  ProviderError,
  ProviderTimeoutError,
  RateLimitError
} from './errors.js'
import { parseJsonContent } from './json.js'

export function isGpt5Family(model) {
  return Boolean(model && String(model).trim().toLowerCase().startsWith('gpt-5'))
}

const MAX_TOKENS = 4096
const DEFAULT_TIMEOUT_MS = 90000

function friendlyHttpError(status, bodyText, url) {
  let detail = ''
  try {
    const body = JSON.parse(bodyText)
    detail = body?.error?.message || body?.message || ''
  } catch {
    detail = bodyText.slice(0, 200)
  }
  const suffix = detail ? ` — ${detail}` : ''
  if (status === 401 || status === 403) {
    return new MissingCredentialsError(
      `The AI endpoint rejected the configured credentials (HTTP ${status})${suffix}`,
      { hint: 'Check the API key and that it is valid for this endpoint.' }
    )
  }
  if (status === 429) {
    return new RateLimitError(`The AI endpoint rate-limited the request (HTTP 429)${suffix}`, {
      hint: 'Wait a moment and try again, or switch to a model with more quota.'
    })
  }
  return new ProviderError(`The AI endpoint returned HTTP ${status}${suffix}`, {
    hint: `Request to ${url} failed. Check the base URL and model name.`
  })
}

export class BrowserLLMProvider {
  providerName = 'browser-openai-compatible'
  isMock = false

  constructor({ apiKey, baseUrl, model, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
    if (!apiKey) {
      throw new MissingCredentialsError(
        'No AI API key configured for browser-side generation.',
        { hint: 'Add your API key in Run settings, or choose the Demo engine.' }
      )
    }
    this.apiKey = apiKey
    this.modelName = model || 'gpt-4o-mini'
    this.baseUrl = (baseUrl || 'https://api.openai.com/v1').replace(/\/+$/, '')
    this.timeoutMs = timeoutMs
    this._responseFormatSupported = true
  }

  async chatJSON(messages, { temperature = 0.3, maxAttempts = 2 } = {}) {
    let lastError = null
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      let payload
      try {
        payload = await this._request(messages, temperature)
      } catch (err) {
        if (err instanceof MalformedResponseError) {
          lastError = err
          if (attempt >= maxAttempts) throw err
          continue
        }
        throw err
      }
      try {
        return this._parsePayload(payload)
      } catch (err) {
        if (!(err instanceof MalformedResponseError)) throw err
        lastError = err
        if (attempt >= maxAttempts) throw err
      }
    }
    throw lastError ?? new MalformedResponseError('The AI model did not produce a JSON response.')
  }

  _buildBody(messages, temperature) {
    const body = {
      model: this.modelName,
      messages
    }
    if (!isGpt5Family(this.modelName)) body.temperature = temperature
    if (isGpt5Family(this.modelName)) body.max_completion_tokens = MAX_TOKENS
    else body.max_tokens = MAX_TOKENS
    if (this._responseFormatSupported) body.response_format = { type: 'json_object' }
    return body
  }

  async _request(messages, temperature) {
    const url = `${this.baseUrl}/chat/completions`
    const maxRetries = 2
    let delay = 1200
    for (let attempt = 0; ; attempt += 1) {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), this.timeoutMs)
      let response
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.apiKey}`
          },
          body: JSON.stringify(this._buildBody(messages, temperature)),
          signal: controller.signal
        })
      } catch (err) {
        clearTimeout(timer)
        if (err?.name === 'AbortError') {
          throw new ProviderTimeoutError(
            `The AI endpoint did not respond within ${Math.round(this.timeoutMs / 1000)}s.`,
            { hint: 'Try again, or use a faster model or endpoint.' }
          )
        }
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, delay))
          delay *= 2
          continue
        }
        throw new ProviderError(`Cannot reach the AI endpoint (${err.message || err}).`, {
          hint:
            'Check the base URL. Some providers block browser (CORS) requests — ' +
            'OpenAI, OpenRouter, Groq and Together generally allow them; if yours does not, ' +
            'use the local DESNWORLD API server or the GitHub Actions workflow instead.'
        })
      }
      clearTimeout(timer)

      if (response.status === 400 && this._responseFormatSupported) {
        const bodyText = await response.text()
        if (/response_format/i.test(bodyText)) {
          // capability negotiation: downgrade to prompt-only JSON guidance
          this._responseFormatSupported = false
          continue
        }
        throw friendlyHttpError(400, bodyText, url)
      }
      if ((response.status === 429 || response.status >= 500) && attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, delay))
        delay *= 2
        continue
      }
      if (!response.ok) {
        const bodyText = await response.text()
        throw friendlyHttpError(response.status, bodyText, url)
      }
      return response.json()
    }
  }

  _parsePayload(payload) {
    const choice = payload?.choices?.[0]
    if (!choice) {
      throw new MalformedResponseError('The AI endpoint returned no choices.')
    }
    const finishReason = choice.finish_reason ?? 'stop'
    let content = choice.message?.content ?? ''
    if (Array.isArray(content)) {
      content = content
        .map((part) => (typeof part === 'string' ? part : part?.text?.value ?? part?.text ?? ''))
        .join('')
    }
    return parseJsonContent(String(content), finishReason)
  }
}

/** Test double: queued results or queued exceptions. */
export class ScriptedProvider {
  providerName = 'scripted'
  modelName = 'scripted-test-double'
  isMock = false

  constructor(queue) {
    this.queue = [...queue]
    this.calls = []
  }

  async chatJSON(messages) {
    this.calls.push(messages)
    if (!this.queue.length) throw new ProviderError('ScriptedProvider queue is empty')
    const item = this.queue.shift()
    if (item instanceof Error) throw item
    return item
  }
}
