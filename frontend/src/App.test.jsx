import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, test, expect } from 'vitest';
import App from './App.jsx';

const result = { request_id: 'test-id', mode: 'demo', provider: 'demo', brief: { summary: 'Review the request.', category: 'support', next_steps: ['Review the source.'], source_ids: [] }, citations: [{ source_id: 'account:1', document: 'account.md', excerpt: 'A fictional policy.' }], warning: 'Offline demo template.', needs_human_review: true };

function mockFetch(processResponse) {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ demo_mode: true, access_code_required: false }) }).mockImplementation(processResponse);
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

test('sample input produces a reviewable brief, source evidence, and JSON', async () => {
  const fetch = mockFetch(async () => ({ ok: true, json: async () => result }));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Offline demo');
  await user.click(screen.getByRole('button', { name: /Account access/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  await screen.findByText('Review the request.');
  expect(screen.getByText('Human review required')).toBeTruthy();
  expect(screen.getByLabelText('AI provider: Demo')).toBeTruthy();
  await user.click(screen.getByText('account.md'));
  expect(screen.getByText('A fictional policy.')).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'JSON' }));
  expect(screen.getByText(/"needs_human_review": true/)).toBeTruthy();
  const body = JSON.parse(fetch.mock.calls[1][1].body);
  expect(body.text).toContain('password reset');
  expect(body.use_references).toBe(true);
  expect(body.website).toBe('');
});

test('a network retry reuses the request ID and new run changes it', async () => {
  let calls = 0;
  const fetch = mockFetch(async () => {
    if (++calls === 1) throw new Error('Connection failed');
    return { ok: true, json: async () => result };
  });
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Offline demo');
  await user.click(screen.getByRole('button', { name: /Account access/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  await screen.findByRole('alert');
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  await screen.findByText('Review the request.');
  expect(JSON.parse(fetch.mock.calls[1][1].body).request_id).toBe(JSON.parse(fetch.mock.calls[2][1].body).request_id);
  await user.click(screen.getByRole('button', { name: /Start a new run/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  await screen.findByText('Review the request.');
  expect(JSON.parse(fetch.mock.calls[3][1].body).request_id).not.toBe(JSON.parse(fetch.mock.calls[2][1].body).request_id);
});

test('server errors are visible and reference toggle is submitted', async () => {
  const fetch = mockFetch(async () => ({ ok: false, json: async () => ({ detail: 'Request limit reached.' }) }));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Offline demo');
  await user.click(screen.getByRole('button', { name: /Refund request/ }));
  await user.click(screen.getByRole('checkbox'));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  expect((await screen.findByRole('alert')).textContent).toBe('Request limit reached.');
  expect(JSON.parse(fetch.mock.calls[1][1].body).use_references).toBe(false);
});

test('live access code is entered by the user and sent only as authorization', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ demo_mode: false, access_code_required: true }) }).mockResolvedValue({ ok: true, json: async () => ({ ...result, mode: 'live', provider: 'openai' }) });
  vi.stubGlobal('fetch', fetch);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Live workspace');
  await user.type(screen.getByLabelText('Workspace access code'), 'synthetic-code');
  await user.click(screen.getByRole('button', { name: /Account access/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  await screen.findByText('Review the request.');
  expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer synthetic-code');
  expect(fetch.mock.calls[1][1].body).not.toContain('synthetic-code');
  expect(screen.getByLabelText('AI provider: OpenAI')).toBeTruthy();
});

test('an HTML gateway error shows a friendly message instead of a JSON parser error', async () => {
  mockFetch(async () => ({ ok: false, status: 502, json: async () => { throw new SyntaxError('Unexpected token < in HTML'); } }));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Offline demo');
  await user.click(screen.getByRole('button', { name: /Account access/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  const alert = await screen.findByRole('alert');
  expect(alert.textContent).toContain('temporarily unavailable');
  expect(alert.textContent).not.toContain('Unexpected token');
});

test('Anthropic quota fallback displays provider attribution and owner billing guidance', async () => {
  mockFetch(async () => ({ ok: true, json: async () => ({ ...result, mode: 'fallback', provider: 'anthropic', error_code: 'provider_quota', warning: 'The service owner must check provider billing or credits before AI processing can resume.' }) }));
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('Offline demo');
  await user.click(screen.getByRole('button', { name: /Account access/ }));
  await user.click(screen.getByRole('button', { name: /Generate brief/ }));
  expect(await screen.findByLabelText('AI provider: Anthropic')).toBeTruthy();
  expect(screen.getByText(/service owner must check provider billing/)).toBeTruthy();
  expect(screen.getByText('fallback')).toBeTruthy();
});
