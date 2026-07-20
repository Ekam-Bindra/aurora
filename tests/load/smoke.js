import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/api/v1';
const EMAIL = __ENV.EMAIL || 'cfo@nimbus.test';
const PASSWORD = __ENV.PASSWORD || 'aurora-demo-2026';

// Login once and share the token across VUs/iterations. Logging in per
// iteration trips the auth rate limiter (brute-force protection working as
// designed) and is not how real clients behave.
export function setup() {
  const login = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(login, { 'setup login 200': (r) => r.status === 200 });
  if (login.status !== 200) {
    throw new Error(`login failed: ${login.status} ${login.body}`);
  }
  return { token: login.json('access_token') };
}

export default function (data) {
  const authHeaders = { Authorization: `Bearer ${data.token}` };

  const health = http.get(`${BASE_URL}/health`);
  check(health, { 'health status 200': (r) => r.status === 200 });

  const metrics = http.get(`${BASE_URL}/metrics/overview`, { headers: authHeaders });
  check(metrics, {
    'metrics ok or no-db 422': (r) => r.status === 200 || r.status === 422,
  });

  const reports = http.get(`${BASE_URL}/board-reports`, { headers: authHeaders });
  check(reports, { 'board-reports 200': (r) => r.status === 200 });

  const risk = http.get(`${BASE_URL}/risk/genome`, { headers: authHeaders });
  check(risk, {
    'risk genome ok or no-db 422': (r) => r.status === 200 || r.status === 422,
  });

  sleep(0.5);
}
