import { type Page, type Locator, expect } from '@playwright/test';

export class KnowledgeDetailPage {
  readonly heading: Locator;
  readonly documentList: Locator;
  readonly uploadDropzone: Locator;
  readonly documentRows: Locator;
  readonly processingStatus: Locator;
  readonly chooseFileButton: Locator;

  constructor(private page: Page) {
    this.heading = page.getByRole('heading', { name: 'Documents' });
    this.documentList = page.locator('table');
    this.uploadDropzone = page.getByRole('region', { name: 'Upload dropzone' });
    this.documentRows = page.locator('table tbody tr');
    this.processingStatus = page.getByText('Processing document');
    this.chooseFileButton = page.getByText('Choose File');
  }

  async goto(kbId: string) {
    await this.page.goto(`/knowledge/${kbId}`);
  }

  async getDocuments() {
    const rows = await this.documentRows.count();
    const documents: Array<{ name: string; status: string }> = [];
    for (let i = 0; i < rows; i++) {
      const row = this.documentRows.nth(i);
      const cells = row.locator('td');
      const name = await cells.nth(0).textContent() ?? '';
      const status = await cells.nth(2).textContent() ?? '';
      documents.push({ name: name.trim(), status: status.trim() });
    }
    return documents;
  }

  async uploadFile(filePath: string) {
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
  }

  async waitForProcessing() {
    await expect(this.processingStatus).toBeVisible({ timeout: 10000 });
    await expect(this.processingStatus).toBeHidden({ timeout: 60000 });
  }

  async getDocumentStatus(filename: string): Promise<string> {
    const documents = await this.getDocuments();
    const doc = documents.find((d) => d.name.includes(filename));
    return doc?.status ?? "";
  }

  async waitForDocumentCompleted(filename: string, timeout = 60000) {
    await expect(async () => {
      const documents = await this.getDocuments();
      const doc = documents.find((d) => d.name.includes(filename));
      expect(doc).toBeDefined();
      expect(doc!.status).toMatch(/Completed|completed|已完成/);
    }).toPass({ timeout });
  }
}
