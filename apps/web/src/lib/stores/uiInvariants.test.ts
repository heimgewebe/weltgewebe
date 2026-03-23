import { describe, it, expect } from 'vitest';
import { assertUiStateInvariant } from './uiInvariants';

const mockSelection = { type: 'node' as const, id: '123' };
const mockDraft = { mode: 'new-knoten' as const, source: 'action-bar' as const };

describe('assertUiStateInvariant', () => {
	it('passes for navigation with no selection and no draft', () => {
		expect(() => assertUiStateInvariant('navigation', null, null)).not.toThrow();
	});

	it('passes for fokus with selection and no draft', () => {
		expect(() => assertUiStateInvariant('fokus', mockSelection, null)).not.toThrow();
	});

	it('passes for komposition with draft and no selection', () => {
		expect(() => assertUiStateInvariant('komposition', null, mockDraft)).not.toThrow();
	});

	it('throws when both selection and draft are set', () => {
		expect(() => assertUiStateInvariant('fokus', mockSelection, mockDraft)).toThrow(
			'selection and kompositionDraft cannot both be set',
		);
	});

	it('throws when fokus has no selection', () => {
		expect(() => assertUiStateInvariant('fokus', null, null)).toThrow(
			"systemState is 'fokus' but selection is null",
		);
	});

	it('throws when navigation has selection', () => {
		expect(() => assertUiStateInvariant('navigation', mockSelection, null)).toThrow(
			"systemState is 'navigation' but selection is not null",
		);
	});

	it('throws when komposition has no draft', () => {
		expect(() => assertUiStateInvariant('komposition', null, null)).toThrow(
			"systemState is 'komposition' but kompositionDraft is null",
		);
	});

	it('throws when not komposition but draft is set', () => {
		expect(() => assertUiStateInvariant('navigation', null, mockDraft)).toThrow(
			"systemState is not 'komposition' but kompositionDraft is not null",
		);
	});
});
