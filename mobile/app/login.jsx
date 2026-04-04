import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../context/AuthContext';

export default function LoginScreen() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const { login } = useAuth();
  const router    = useRouter();

  const handleLogin = async () => {
    if (!username || !password) {
      setError('Please fill in all fields');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      router.replace('/dashboard');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.card}>
        <Text style={styles.title}>AI Project Intelligence</Text>
        <Text style={styles.subtitle}>Sign in to your account</Text>

        {error && <Text style={styles.error}>{error}</Text>}

        <TextInput
          style={styles.input}
          placeholder="Username"
          placeholderTextColor="#999"
          autoCapitalize="none"
          value={username}
          onChangeText={setUsername}
        />

        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#999"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.buttonText}>Sign In</Text>
          }
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container:      { flex: 1, backgroundColor: '#F5F7FA', justifyContent: 'center', padding: 24 },
  card:           { backgroundColor: '#fff', borderRadius: 16, padding: 28, shadowColor: '#000',
                    shadowOpacity: 0.08, shadowRadius: 12, elevation: 4 },
  title:          { fontSize: 22, fontWeight: 'bold', color: '#002B5C', textAlign: 'center', marginBottom: 6 },
  subtitle:       { fontSize: 14, color: '#666', textAlign: 'center', marginBottom: 24 },
  input:          { borderWidth: 1, borderColor: '#DDE3ED', borderRadius: 10, padding: 14,
                    fontSize: 15, color: '#333', marginBottom: 14, backgroundColor: '#FAFBFC' },
  button:         { backgroundColor: '#0066B3', borderRadius: 10, padding: 16, alignItems: 'center' },
  buttonDisabled: { opacity: 0.6 },
  buttonText:     { color: '#fff', fontSize: 16, fontWeight: '600' },
  error:          { backgroundColor: '#FFF0F0', color: '#CC0000', padding: 10, borderRadius: 8,
                    marginBottom: 14, fontSize: 13, textAlign: 'center' },
});