#!/usr/bin/env node

import { exec } from 'node:child_process';
import { promisify } from 'util';
const execPromise = promisify(exec);

import { readFile as readFilePromise } from 'node:fs/promises';
import { launch } from 'puppeteer';
import { parse } from 'ts-command-line-args';

import * as bitwarden from './bitwarden';
import * as github from './github';

interface OctopuppetArguments {
  organizationFile?: string;
  puppeteerFile: string;
  help?: boolean;
}

export const args = parse<OctopuppetArguments>(
  {
    organizationFile: { type: String, alias: 'f', optional: true },
    puppeteerFile: { type: String, alias: 'p' },
    help: { type: Boolean, optional: true, alias: 'h', description: 'Prints this usage guide' },
  },
  {
      helpArg: 'help',
  },
);

(async () => {
  const organization = await readJsonFile(args.organizationFile);
  const puppeteer = await readJsonFile(args.puppeteerFile);

  const browser = await launch({ headless: true, userDataDir: './.pupeteer_data' })

  const page = await (async () => {
    const pages = await browser.pages();
    if (pages.length > 0) {
      return Promise.resolve(pages[0]);
    } else {
      return browser.newPage()
    }
  })();

  const creds = new bitwarden.BitwardenCredentials(organization.auth.item_id);
  const loginWorkflow = new github.LoginWorkflow(page);
  await loginWorkflow.loginIfRequired(page, creds);

  for (const [settingsPage, settings] of Object.entries(organization.puppeteer)) {
    await page.goto(`https://github.com/organizations/${organization.login}/${settingsPage}`)
    var headerPrinted = false;

    for (const [setting, expectedValue] of Object.entries(settings as any)) {
      const pupetteerSetting = puppeteer[settingsPage][setting];

      const value = await page.$eval(
        pupetteerSetting.selector,
        (el, property) => el[property],
        pupetteerSetting.valueSelector
      );

      if (value !== expectedValue) {
        if (!headerPrinted) {
          console.log(`"${settingsPage}"+: {`);
          headerPrinted = true;
        }
        console.log(`${setting}: ${value},`);
      }
    }

    if (headerPrinted) {
      console.log('},');
    }
  }

  await browser.close();
})();

async function readJsonFile(file?: string): Promise<any> {
  return await readFile(file).then(f => JSON.parse(f));
}

async function readFile(file?: string): Promise<string> {
  if (file === undefined || file.endsWith('-')) {
    return await readFilePromise('/dev/stdin').then(p => p.toString('utf-8'));
  } else if (file.endsWith('.jsonnet')) {
    return await execPromise(`jsonnet ${file}`).then(p => p.stdout);
  } else {
    return await readFilePromise(file).then(p => p.toString('utf-8'));
  }
}

