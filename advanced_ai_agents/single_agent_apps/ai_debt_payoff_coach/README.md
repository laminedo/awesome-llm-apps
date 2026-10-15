# 💳 AI Debt Payoff Coach

A modern, no-install web app that helps you **pay off debt faster** and **track what you spend on each card**, including **IRS tax balances**. Inspired by the [AI Financial Coach Agent](../../multi_agent_apps/ai_financial_coach_agent/) in this repo, rebuilt as a single HTML file so beginners can run it by double-clicking.

## Features

- **Payoff planner**: add credit cards, loans and IRS balances, then compare **Avalanche** (highest rate first) vs **Snowball** (smallest balance first) vs paying only minimums.
- **"Extra per month" slider** that instantly shows your new debt-free date and how much interest you save.
- **Balance chart** month by month, plus the exact order to pay each debt and when each one hits $0.
- **IRS-aware tips**: payment-plan guidance (penalty drops from 0.5% to 0.25%/month), 180-day short-term plans, and an estimated IRS rate you can edit.
- **Expense tracker**: log purchases by card and category, set monthly budgets, and see what's over budget.
- **Credit used** per card (balance vs limit) with score tips.
- **AI coach chat** that knows your real numbers:
  - When opened as a Claude artifact, it uses Claude automatically.
  - When run locally, paste a free [Gemini API key](https://aistudio.google.com/apikey) in the AI coach tab.
- **Rule-based coach notes** that work with no AI at all.
- Light and dark mode, works on phones.
- Data stays in your browser (or your private Claude storage when opened as an artifact). Use **Copy backup** to save a copy.

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
