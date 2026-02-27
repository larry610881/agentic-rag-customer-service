import { type Page, type Locator } from '@playwright/test';

export class LoginPage {
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;
  readonly validationErrors: Locator;

  constructor(private page: Page) {
    this.usernameInput = page.getByLabel('使用者名稱');
    this.passwordInput = page.getByLabel('密碼');
    this.submitButton = page.getByRole('button', { name: '登入' });
    this.errorMessage = page.getByText('登入失敗，請確認帳號密碼是否正確。');
    this.validationErrors = page.locator('.text-destructive');
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(username: string, password: string) {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async getErrorMessage() {
    return this.errorMessage.textContent();
  }

  async getValidationErrors() {
    return this.validationErrors.allTextContents();
  }
}
