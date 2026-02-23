import { test as base } from "@playwright/test";
import { createBdd } from "playwright-bdd";

export const test = base;
export const { Given, When, Then } = createBdd(test);
