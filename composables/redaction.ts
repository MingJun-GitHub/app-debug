const REDACTED = '[REDACTED]'
const KEY_VALUE_PATTERN = /\b(authorization|proxy-authorization|cookie|set-cookie|access[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|client[_-]?secret|private[_-]?key|password|passwd|push[_-]?token|fcm[_-]?token|apns[_-]?token)\b(["']?\s*[:=]\s*["']?)([^"'\s,;}\]]+)/gi
const QUERY_SECRET_PATTERN = /([?&](?:access_token|refresh_token|token|key|signature|sign|password)=)([^&\s#]+)/gi
const BEARER_PATTERN = /\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/gi
const JWT_PATTERN = /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g
const EMAIL_PATTERN = /\b([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]*)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g
const LONG_HEX_PATTERN = /\b(?:[0-9a-fA-F]{40,})\b/g

export function redactSensitive(value: unknown) {
  let text = value == null ? '' : String(value)
  text = text.replace(BEARER_PATTERN, (_match, scheme: string) => `${scheme} ${REDACTED}`)
  text = text.replace(
    KEY_VALUE_PATTERN,
    (_match, key: string, separator: string) => `${key}${separator}${REDACTED}`
  )
  text = text.replace(
    QUERY_SECRET_PATTERN,
    (_match, prefix: string) => `${prefix}${REDACTED}`
  )
  text = text.replace(JWT_PATTERN, '[REDACTED_JWT]')
  text = text.replace(LONG_HEX_PATTERN, '[REDACTED_HEX]')
  text = text.replace(
    EMAIL_PATTERN,
    (_match, first: string, local: string, domain: string) => `${first}***@${domain}`
  )
  return text
}

