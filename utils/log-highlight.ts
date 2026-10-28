export interface HighlightPattern {
  value: string
  regex: boolean
}

export interface HighlightSegment {
  text: string
  highlighted: boolean
}

export function highlightSegments(
  text: string,
  patterns: HighlightPattern[]
): HighlightSegment[] {
  if (!text || !patterns.length) return [{ text, highlighted: false }]
  const ranges: Array<[number, number]> = []

  for (const pattern of patterns) {
    if (!pattern.value) continue
    if (pattern.regex) {
      try {
        const matcher = new RegExp(pattern.value, 'gi')
        let match: RegExpExecArray | null
        let matched = 0
        while ((match = matcher.exec(text)) && matched < 1000) {
          if (!match[0].length) {
            matcher.lastIndex += 1
            continue
          }
          ranges.push([match.index, match.index + match[0].length])
          matched += 1
        }
      } catch {
        // Invalid regexes remain searchable server-side.
      }
      continue
    }

    const needle = pattern.value.toLowerCase()
    const haystack = text.toLowerCase()
    let searchFrom = 0
    while (searchFrom < haystack.length) {
      const index = haystack.indexOf(needle, searchFrom)
      if (index < 0) break
      ranges.push([index, index + needle.length])
      searchFrom = index + Math.max(needle.length, 1)
    }
  }

  if (!ranges.length) return [{ text, highlighted: false }]
  ranges.sort((left, right) => left[0] - right[0])
  const merged: Array<[number, number]> = []
  for (const range of ranges) {
    const previous = merged.at(-1)
    if (previous && range[0] <= previous[1]) {
      previous[1] = Math.max(previous[1], range[1])
    } else {
      merged.push([...range])
    }
  }

  const segments: HighlightSegment[] = []
  let cursor = 0
  for (const [start, end] of merged) {
    if (start > cursor) segments.push({ text: text.slice(cursor, start), highlighted: false })
    segments.push({ text: text.slice(start, end), highlighted: true })
    cursor = end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), highlighted: false })
  return segments
}

