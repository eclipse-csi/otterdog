import { HTTPResponse, Page }  from 'puppeteer';
import { Credentials } from './octopuppet';
import { assert } from 'node:console';

const EMAILS_OPTIONS = 'select[name="user[profile_email]"] > option';

export class LoginWorkflow {
  private readonly page: Page;

  constructor(page: Page) {
    assert(page !== undefined)
    this.page = page;
  }

  async login(creds: Credentials): Promise<HTTPResponse | null> {
    await this.page.goto('https://github.com/login');
    await creds.username().then(username => this.page.type('#login_field', username));
    await creds.password().then(password => this.page.type('#password', password));
    await this.page.click('input[name="commit"]');
    await this.page.waitForNavigation();
    await this.page.goto('https://github.com/sessions/two-factor');
    await creds.totp().then(totp => {this.page.type('#totp', totp as string)});
    return this.page.waitForNavigation();
  }

  async loginIfRequired(page: Page, creds: Credentials): Promise<boolean> {
    const loggedInAs = await this.loggedInAs();
    const credsUsername = await creds.username();

    if (!loggedInAs) {
      return this.login(creds).then(r => r != null && r.status() < 300).catch(err => {throw new Error(err)});
    } else if (credsUsername != loggedInAs && !await page.$$eval(EMAILS_OPTIONS, optionValue()).then(options => options.includes(credsUsername))) {
      await this.logout();
      return this.login(creds).then(r => r != null && r.status() < 300);
    } else {
      return Promise.resolve(false);
    }

    function optionValue(): string | ((options: Element[]) => string[]) {
      return options => options.map(o => (o as HTMLOptionElement).value);
    }
  }

  private async loggedInAs(): Promise<string | undefined> {
    return this.page.goto('https://github.com/settings/profile').then(response => {
      return this.page.$eval('meta[name="octolytics-actor-login"]', el => (el as HTMLMetaElement).content)
    }).catch(err => {
      return undefined;
    });
  }

  async logout(): Promise<HTTPResponse | null> {
    const actor_login = await this.loggedInAs();
    await this.page.goto('https://github.com/settings/profile');
    await this.page.$eval(`div.Header-item > details.details-overlay > summary.Header-link > img[alt="@${actor_login}"]`, el => (el as HTMLButtonElement).click());
    await this.page.waitForSelector('button[type="submit"].dropdown-signout');
    await this.page.$eval('button[type="submit"].dropdown-signout', el => (el as HTMLButtonElement).click());
    return this.page.waitForNavigation();
  }
}