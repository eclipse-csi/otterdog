import { exec } from 'node:child_process';
import { promisify } from 'util';
import { Credentials } from './octopuppet';
const execPromise = promisify(exec);

interface Item {
  login: ItemLogin;
}

interface ItemLogin {
  username: string;
  password: string;
}

export class BitwardenCredentials implements Credentials {

  private readonly itemId: string;
  private _item?: Item = undefined;
  private _lockedVault?: boolean = undefined;

  constructor(itemId: string) {
    this.itemId = itemId;
  }

  async username(): Promise<string> {
    return this.readItem().then(i => {
      return i.login.username;
    }).catch((err) => {
      throw new Error(`Error while getting username from Biwarden item ${this.itemId}`);
    });
  }

  async password(): Promise<string> {
    return this.readItem().then(i => {
      return i.login.password;
    }).catch((err) => {
      throw new Error(`Error while getting password from Biwarden item ${this.itemId}`);
    });
  }

  async totp(): Promise<string|undefined> {
    await this.checkLockedVault();

    return execPromise(`bw get totp ${this.itemId}`)
      .then(p => {
        return p.stdout;
      }).catch(err => {
        console.error(`Error while getting 'totp' for item ${this.itemId}`);
        return Promise.resolve(undefined);
      })
  }

  private async readItem() : Promise<Item> {
    if (this._item === undefined) {
      await this.checkLockedVault();
      return execPromise(`bw get item ${this.itemId}`).then(p => {
        this._item = JSON.parse(p.stdout);
        return this._item as Item;
      }).catch((err) => {
        throw new Error(`Error while getting Biwarden item ${this.itemId}`);
      });
    } else {
      return Promise.resolve(this._item);
    }
  }

  private async checkLockedVault() {
    if (this._lockedVault === undefined) {
      try {
        await execPromise(`bw unlock --check`)
          .then(() => this._lockedVault = false)
          .catch(() => this._lockedVault = true);
      } catch (err) {
        throw new Error('Bitwarden vault is locked. Unlock before using this command');
      }
    } else {
      return Promise.resolve(this._lockedVault);
    }
  }
}
