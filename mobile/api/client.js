const BASE_URL = 'http://192.168.1.11:8000';

const get = async (path, token) => {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

const post = async (path, body, token) => {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
};

export const api = {
  login:            (username, password)  => post('/api/login', { username, password }),
  getMe:            (token)               => get('/api/me', token),
  getDashboard:     (projectKey, token)   => get(`/api/dashboard/${projectKey}`, token),
  getAiInsights:    (projectKey, token)   => get(`/api/ai/${projectKey}`, token),
  getJiraData:      (projectKey, token)   => get(`/api/jira-explorer/${projectKey}`, token),
  getIncidents:     (token)               => get('/api/incidents', token),
  getTeamScorecard: (projectKey, token)   => get(`/api/team-scorecard/${projectKey}`, token),
  getSnapshots:     (projectKey, token)   => get(`/api/snapshots/${projectKey}`, token),
  healthCheck:      ()                    => get('/api/health'),
};