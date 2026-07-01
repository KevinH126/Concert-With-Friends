import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Defaults to the deployed backend so demos work out of the box. For local
// backend work, set EXPO_PUBLIC_API_URL to your machine's LAN IP, e.g.
//   EXPO_PUBLIC_API_URL=http://192.168.1.85:8000
// Update the fallback to your real Render URL after the first deploy.
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://cwf-api.onrender.com';

export const api = axios.create({ baseURL: BASE_URL });

const TOKEN_KEY = 'auth_token';

export async function saveToken(token: string) {
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function loadToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function clearToken() {
  await AsyncStorage.removeItem(TOKEN_KEY);
}

// Attach Bearer token to every request
api.interceptors.request.use(async (config) => {
  const token = await loadToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Let AuthContext react when the token is rejected (expired/invalid).
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

// On 401, drop the stored token and notify the app so it returns to login.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error?.response?.status === 401) {
      await clearToken();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);
