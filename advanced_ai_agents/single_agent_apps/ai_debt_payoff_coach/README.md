# 💳 AI Debt Payoff Coach

A modern, no-install web app that helps you **pay off debt faster** and **track what you spend on each card**, including **IRS tax balances**. Inspired by the [AI Financial Coach Agent](../../multi_agent_apps/ai_financial_coach_agent/) in this repo, rebuilt as a single HTML file so beginners can run it by double-clicking.

## Features

- **Track every purchase**: log purchases by card and category (the category is guessed from the store name), edit them, record refunds, and search or filter by month, card or category.
- **Import from your bank**: drop in the CSV file your bank lets you download. The app finds the date, description and amount columns, skips card payments, auto-categorizes each row and skips duplicates. You can export back to CSV at any time.
- **Repeat charges**: subscriptions and bills that show up every month are found automatically, with your monthly and yearly total.
- **Payoff planner**: compare **Avalanche** (highest rate first), **Snowball** (smallest balance first) and paying only minimums for credit cards, loans and IRS balances. An "extra per month" slider shows your new debt-free date and the interest you save.
- **Payments and due dates**: log payments (your balance updates automatically), see bills due in the next 31 days, and track how much you've paid down on each debt.
- **IRS help**: payment-plan guidance (the late-payment penalty drops from 0.5% to 0.25%/month), 180-day short-term plans, and an estimated IRS rate you can change.
- **Budgets**: set monthly budgets, add your own categories, and see a 6-month spending trend and spending per card.
- **AI coach** that knows your numbers: it uses Claude when opened as a claude.ai artifact, or a free [Gemini API key](https://aistudio.google.com/apikey) when run locally. Rule-based coach notes work with no AI at all.
- Light and dark mode, with a phone-friendly bottom tab bar.

## Security & privacy

- The app never asks for bank logins, card numbers or SSNs.
- CSV files are read on your device. Nothing is uploaded.
- Data lives in your browser (local file), or privately in your Claude account (claude.ai artifact). Use **Save backup file** to keep a copy.
- Everything you import (CSV files, backups, saved data) is validated, and everything shown on screen is escaped to block script injection.
- `index.html` ships with a strict Content Security Policy: only the app's own script can run, and the app can only talk to Google Fonts and the Gemini API.
- Exported CSV files are protected against spreadsheet formula injection.
- Your Gemini key is kept only in your browser and sent only to Google, in a request header.

## How to run

1. Download or clone the repo:
   ```bash
   git clone https://github.com/Shubhamsaboo/awesome-llm-apps.git
   cd awesome-llm-apps/advanced_ai_agents/single_agent_apps/ai_debt_payoff_coach
   ```
2. Double-click `index.html` (or open it in Chrome, Edge, Safari or Firefox). That's it!

## Editing the app

- `app.html` holds the page content (styles, layout and JavaScript).
- After editing it, run `./build.sh` to regenerate `index.html`.

## Disclaimer

This app is for general education only. It is not professional financial or tax advice. For IRS questions, see [irs.gov/payments](https://www.irs.gov/payments) or talk to a tax professional.
