import { describe, it, expect } from 'vitest';
import { rewritePmtilesUrl, resolveBasemapStyle } from './basemap';

describe('rewritePmtilesUrl', () => {
	it('rewrites bare pmtiles alias to local dev proxy', () => {
		const result = rewritePmtilesUrl(
			'pmtiles://basemap-hamburg.pmtiles',
			'http://localhost:5173',
		);
		expect(result).toBe(
			'pmtiles://http://localhost:5173/local-basemap/basemap-hamburg.pmtiles',
		);
	});

	it('leaves fully qualified pmtiles URLs unchanged', () => {
		const result = rewritePmtilesUrl(
			'pmtiles://example.com/path/tiles.pmtiles',
			'http://localhost:5173',
		);
		expect(result).toBe('pmtiles://example.com/path/tiles.pmtiles');
	});

	it('leaves non-pmtiles URLs unchanged', () => {
		const result = rewritePmtilesUrl(
			'https://example.com/style.json',
			'http://localhost:5173',
		);
		expect(result).toBe('https://example.com/style.json');
	});

	it('leaves empty string unchanged', () => {
		expect(rewritePmtilesUrl('', 'http://localhost:5173')).toBe('');
	});
});

describe('resolveBasemapStyle', () => {
	it('returns styleUrl for remote-style mode', () => {
		const result = resolveBasemapStyle({
			mode: 'remote-style',
			styleUrl: 'https://example.com/style.json',
		} as any);
		expect(result).toBe('https://example.com/style.json');
	});

	it('throws when remote-style has no styleUrl', () => {
		expect(() => resolveBasemapStyle({ mode: 'remote-style' } as any)).toThrow(
			'styleUrl required',
		);
	});

	it('returns local path for local-sovereign mode', () => {
		const result = resolveBasemapStyle({ mode: 'local-sovereign' } as any);
		expect(result).toBe('/local-basemap/style.json');
	});
});
