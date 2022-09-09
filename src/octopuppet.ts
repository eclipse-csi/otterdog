export interface Credentials {
  username(): Promise<string>;
  password(): Promise<string>;
  totp(): Promise<string|undefined>;
}

export { BitwardenCredentials } from './bitwarden';