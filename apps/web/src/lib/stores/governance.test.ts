import { describe, it, expect, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('$app/environment', () => ({ browser: false, dev: false }));

import { createBooleanToggle } from './governance';

describe('createBooleanToggle', () => {
	it('starts with initial value (default false)', () => {
		const toggle = createBooleanToggle();
		expect(get(toggle)).toBe(false);
	});

	it('starts with custom initial value', () => {
		const toggle = createBooleanToggle(true);
		expect(get(toggle)).toBe(true);
	});

	it('open sets to true', () => {
		const toggle = createBooleanToggle(false);
		toggle.open();
		expect(get(toggle)).toBe(true);
	});

	it('close sets to false', () => {
		const toggle = createBooleanToggle(true);
		toggle.close();
		expect(get(toggle)).toBe(false);
	});

	it('toggle flips value', () => {
		const toggle = createBooleanToggle(false);
		toggle.toggle();
		expect(get(toggle)).toBe(true);
		toggle.toggle();
		expect(get(toggle)).toBe(false);
	});
});
