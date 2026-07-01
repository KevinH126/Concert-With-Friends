import { api } from './client';
import { FriendUser } from './friends';

export interface Invite {
  token: string;
  url: string;
  max_uses: number;
  expires_at: string;
}

export async function createInvite(): Promise<Invite> {
  const { data } = await api.post('/invites');
  return data;
}

// Accepts either the raw code or a pasted invite URL.
export function extractInviteCode(input: string): string {
  const trimmed = input.trim();
  const segments = trimmed.split('/').filter(Boolean);
  return (segments.length > 1 ? segments[segments.length - 1] : trimmed).toLowerCase();
}

export async function redeemInvite(codeOrUrl: string): Promise<FriendUser> {
  const token = extractInviteCode(codeOrUrl);
  const { data } = await api.post(`/invites/${token}/redeem`);
  return data.friend;
}
