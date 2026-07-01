import { api, saveToken, clearToken } from './client';

export interface User {
  id: string;
  email: string;
  username: string | null;
  display_name: string;
  home_metro_id: string | null;
  location_precision: string;
}

export async function signup(
  email: string,
  username: string,
  displayName: string,
  password: string,
  homeMetroId?: string,
): Promise<void> {
  const { data } = await api.post('/auth/signup', {
    email,
    username,
    display_name: displayName,
    password,
    home_metro_id: homeMetroId ?? null,
  });
  await saveToken(data.access_token);
}

export async function login(email: string, password: string): Promise<void> {
  const { data } = await api.post('/auth/login', { email, password });
  await saveToken(data.access_token);
}

export async function logout(): Promise<void> {
  await clearToken();
}

export async function getMe(): Promise<User> {
  const { data } = await api.get('/auth/me');
  return data;
}

export async function updateProfile(patch: {
  display_name?: string;
  username?: string;
  home_metro_id?: string;
  location_precision?: string;
}): Promise<User> {
  const { data } = await api.patch('/users/me', patch);
  return data;
}
