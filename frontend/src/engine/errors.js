/**
 * Structured error types for the in-browser DESNWORLD engine.
 * Mirrors engine/desnworld/errors.py so both runtimes surface the same codes.
 */

export class EngineError extends Error {
  constructor(message, { hint = '', code = 'engine_error', problems = [] } = {}) {
    super(message)
    this.name = new.target.name
    this.code = code
    this.hint = hint
    this.problems = problems
  }

  toPayload() {
    const payload = { error: this.code, message: this.message }
    if (this.hint) payload.hint = this.hint
    if (this.problems?.length) payload.problems = this.problems
    return payload
  }
}

export class InputValidationError extends EngineError {
  constructor(message, options = {}) {
    super(message, { code: 'input_validation_error', ...options })
  }
}

export class MissingCredentialsError extends EngineError {
  constructor(message, options = {}) {
    super(message, { code: 'missing_credentials', ...options })
  }
}

export class ProviderError extends EngineError {
  constructor(message, options = {}) {
    super(message, { code: 'provider_error', ...options })
  }
}

export class RateLimitError extends ProviderError {
  constructor(message, options = {}) {
    super(message, { code: 'rate_limit_error', ...options })
  }
}

export class ProviderTimeoutError extends ProviderError {
  constructor(message, options = {}) {
    super(message, { code: 'provider_timeout', ...options })
  }
}

export class MalformedResponseError extends ProviderError {
  constructor(message, options = {}) {
    super(message, { code: 'malformed_response', ...options })
  }
}

export class SchemaValidationError extends EngineError {
  constructor(message, options = {}) {
    super(message, { code: 'schema_validation_error', ...options })
  }
}
