import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, ActivityIndicator, RefreshControl, FlatList
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

// ── Small reusable components ──────────────────────────────────

function MetricCard({ label, value, color }) {
  return (
    <View style={[styles.metricCard, { borderLeftColor: color || '#0066B3' }]}>
      <Text style={styles.metricValue}>{value ?? '—'}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function HealthBadge({ health }) {
  const colorMap = {
    healthy:  { bg: '#E6F4EA', text: '#1E7E34' },
    warning:  { bg: '#FFF8E1', text: '#B8860B' },
    critical: { bg: '#FDECEA', text: '#CC0000' },
  };
  const key    = health?.toLowerCase() || 'warning';
  const colors = colorMap[key] || colorMap.warning;
  return (
    <View style={[styles.healthBadge, { backgroundColor: colors.bg }]}>
      <Text style={[styles.healthText, { color: colors.text }]}>
        {health || 'Unknown'}
      </Text>
    </View>
  );
}

function SectionHeader({ title }) {
  return <Text style={styles.sectionHeader}>{title}</Text>;
}

// ── Main Dashboard Screen ──────────────────────────────────────

export default function DashboardScreen() {
  const { token, user, logout } = useAuth();
  const router = useRouter();

  const [projects, setProjects]         = useState([]);
  const [selectedKey, setSelectedKey]   = useState(null);
  const [data, setData]                 = useState(null);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [error, setError]               = useState(null);

  // Load dashboard for a given project key
  const loadDashboard = async (projectKey, silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboard(projectKey, token);
      setData(res);
      setProjects(res.projects || []);
      setSelectedKey(res.project_key);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!token) {
      router.replace('/login');
      return;
    }
    loadDashboard(null); // backend picks default project
  }, [token]);

  const onRefresh = () => {
    setRefreshing(true);
    loadDashboard(selectedKey, true);
  };

  const handleLogout = () => {
    logout();
    router.replace('/login');
  };

  // ── Loading state ──
  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#0066B3" />
        <Text style={styles.loadingText}>Loading dashboard...</Text>
      </View>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => loadDashboard(selectedKey)}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const metrics = data?.metrics || {};
  const health  = data?.project_health;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* ── Header ── */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Dashboard</Text>
          <Text style={styles.headerSub}>Welcome, {user?.username}</Text>
        </View>
        <TouchableOpacity onPress={handleLogout} style={styles.logoutBtn}>
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </View>

      {/* ── Project Selector ── */}
      {projects.length > 0 && (
        <>
          <SectionHeader title="Projects" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.projectRow}>
            {projects.map((p) => {
              const key    = p.identity?.project_key;
              const active = key === selectedKey;
              return (
                <TouchableOpacity
                  key={key}
                  style={[styles.projectChip, active && styles.projectChipActive]}
                  onPress={() => loadDashboard(key)}
                >
                  <Text style={[styles.projectChipText, active && styles.projectChipTextActive]}>
                    {p.identity?.project_name || key}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </>
      )}

      {/* ── Project Health ── */}
      <View style={styles.healthRow}>
        <Text style={styles.projectKeyLabel}>{selectedKey}</Text>
        <HealthBadge health={health} />
      </View>

      {/* ── Key Metrics ── */}
      <SectionHeader title="Key Metrics" />
      <View style={styles.metricsGrid}>
        <MetricCard label="Total Issues"     value={metrics.total_issues}      color="#0066B3" />
        <MetricCard label="Open Issues"      value={metrics.open_issues}       color="#E67E22" />
        <MetricCard label="Done"             value={metrics.done_count}         color="#27AE60" />
        <MetricCard label="In Progress"      value={metrics.in_progress_count}  color="#8E44AD" />
        <MetricCard label="Avg Cycle Time"   value={metrics.avg_cycle_time_days != null
                                                    ? `${metrics.avg_cycle_time_days}d` : '—'}
                                             color="#2980B9" />
        <MetricCard label="Overdue"          value={metrics.overdue_count}     color="#CC0000" />
      </View>

      {/* ── Status Breakdown ── */}
      {data?.chart_data?.labels?.length > 0 && (
        <>
          <SectionHeader title="Status Breakdown" />
          <View style={styles.card}>
            {data.chart_data.labels.map((label, i) => {
              const total = data.chart_data.values.reduce((a, b) => a + b, 0);
              const val   = data.chart_data.values[i];
              const pct   = total > 0 ? Math.round((val / total) * 100) : 0;
              return (
                <View key={label} style={styles.barRow}>
                  <Text style={styles.barLabel}>{label}</Text>
                  <View style={styles.barTrack}>
                    <View style={[styles.barFill, { width: `${pct}%` }]} />
                  </View>
                  <Text style={styles.barValue}>{val} ({pct}%)</Text>
                </View>
              );
            })}
          </View>
        </>
      )}

      {/* ── Assignee WIP ── */}
      {data?.assignee_chart_data?.labels?.length > 0 && (
        <>
          <SectionHeader title="Assignee Workload" />
          <View style={styles.card}>
            {data.assignee_chart_data.labels.map((label, i) => (
              <View key={label} style={styles.assigneeRow}>
                <View style={styles.assigneeAvatar}>
                  <Text style={styles.assigneeInitial}>
                    {label?.charAt(0)?.toUpperCase() || '?'}
                  </Text>
                </View>
                <Text style={styles.assigneeName}>{label}</Text>
                <Text style={styles.assigneeCount}>
                  {data.assignee_chart_data.values[i]} issues
                </Text>
              </View>
            ))}
          </View>
        </>
      )}

      {/* ── Recent Issues ── */}
      {data?.issues_table?.length > 0 && (
        <>
          <SectionHeader title={`Recent Issues (${data.total_issues} total)`} />
          <View style={styles.card}>
            {data.issues_table.slice(0, 10).map((issue, i) => (
              <View key={issue.key || i} style={styles.issueRow}>
                <View style={styles.issueLeft}>
                  <Text style={styles.issueKey}>{issue.key}</Text>
                  <Text style={styles.issueSummary} numberOfLines={2}>
                    {issue.summary}
                  </Text>
                </View>
                <View style={[
                  styles.statusBadge,
                  issue.status === 'Done' && styles.statusDone,
                  issue.status === 'In Progress' && styles.statusInProgress,
                ]}>
                  <Text style={styles.statusText}>{issue.status}</Text>
                </View>
              </View>
            ))}
          </View>
        </>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ── Styles ────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:          { flex: 1, backgroundColor: '#F5F7FA' },
  center:             { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  loadingText:        { marginTop: 12, color: '#666', fontSize: 14 },
  errorText:          { color: '#CC0000', fontSize: 15, textAlign: 'center', marginBottom: 16 },
  retryButton:        { backgroundColor: '#0066B3', paddingHorizontal: 24, paddingVertical: 10,
                        borderRadius: 8 },
  retryText:          { color: '#fff', fontWeight: '600' },

  // Header
  header:             { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
                        backgroundColor: '#002B5C', padding: 20, paddingTop: 56 },
  headerTitle:        { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  headerSub:          { fontSize: 13, color: '#A8C4E0', marginTop: 2 },
  logoutBtn:          { backgroundColor: 'rgba(255,255,255,0.15)', paddingHorizontal: 14,
                        paddingVertical: 7, borderRadius: 8 },
  logoutText:         { color: '#fff', fontSize: 13, fontWeight: '500' },

  // Project chips
  projectRow:         { paddingHorizontal: 16, marginBottom: 8 },
  projectChip:        { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 20, paddingHorizontal: 14,
                        paddingVertical: 6, marginRight: 8, backgroundColor: '#fff' },
  projectChipActive:  { backgroundColor: '#0066B3', borderColor: '#0066B3' },
  projectChipText:    { fontSize: 13, color: '#555' },
  projectChipTextActive: { color: '#fff', fontWeight: '600' },

  // Health row
  healthRow:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
                        paddingHorizontal: 16, marginBottom: 4 },
  projectKeyLabel:    { fontSize: 16, fontWeight: '700', color: '#002B5C' },
  healthBadge:        { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  healthText:         { fontSize: 13, fontWeight: '600' },

  // Section headers
  sectionHeader:      { fontSize: 13, fontWeight: '700', color: '#888', textTransform: 'uppercase',
                        letterSpacing: 0.8, paddingHorizontal: 16, marginTop: 20, marginBottom: 10 },

  // Metrics grid
  metricsGrid:        { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12 },
  metricCard:         { width: '46%', margin: '2%', backgroundColor: '#fff', borderRadius: 12,
                        padding: 16, borderLeftWidth: 4, shadowColor: '#000',
                        shadowOpacity: 0.05, shadowRadius: 6, elevation: 2 },
  metricValue:        { fontSize: 22, fontWeight: 'bold', color: '#002B5C' },
  metricLabel:        { fontSize: 12, color: '#777', marginTop: 4 },

  // Card wrapper
  card:               { marginHorizontal: 16, backgroundColor: '#fff', borderRadius: 12, padding: 16,
                        shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 6, elevation: 2 },

  // Status bars
  barRow:             { marginBottom: 12 },
  barLabel:           { fontSize: 13, color: '#444', marginBottom: 4 },
  barTrack:           { height: 8, backgroundColor: '#EEF2F7', borderRadius: 4, overflow: 'hidden' },
  barFill:            { height: 8, backgroundColor: '#0066B3', borderRadius: 4 },
  barValue:           { fontSize: 12, color: '#777', marginTop: 3 },

  // Assignees
  assigneeRow:        { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  assigneeAvatar:     { width: 34, height: 34, borderRadius: 17, backgroundColor: '#0066B3',
                        justifyContent: 'center', alignItems: 'center', marginRight: 10 },
  assigneeInitial:    { color: '#fff', fontWeight: 'bold', fontSize: 15 },
  assigneeName:       { flex: 1, fontSize: 14, color: '#333' },
  assigneeCount:      { fontSize: 13, color: '#888' },

  // Issues table
  issueRow:           { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between',
                        paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F0F4F8' },
  issueLeft:          { flex: 1, paddingRight: 10 },
  issueKey:           { fontSize: 12, color: '#0066B3', fontWeight: '600', marginBottom: 2 },
  issueSummary:       { fontSize: 13, color: '#444' },
  statusBadge:        { backgroundColor: '#EEF2F7', paddingHorizontal: 8, paddingVertical: 3,
                        borderRadius: 8, alignSelf: 'flex-start' },
  statusDone:         { backgroundColor: '#E6F4EA' },
  statusInProgress:   { backgroundColor: '#FFF8E1' },
  statusText:         { fontSize: 11, color: '#555', fontWeight: '500' },
});