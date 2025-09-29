import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 1, iterations: 3 };

export default function () {
  const res1 = http.get(`${__ENV.BASE_URL}/health/live`);
  check(res1, { 'live 200': r => r.status === 200 });

  const res2 = http.get(`${__ENV.BASE_URL}/health/ready`);
  check(res2, { 'ready 2xx/5xx': r => r.status === 200 || r.status === 503 });
}
