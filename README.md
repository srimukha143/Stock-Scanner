# Holdings scanner

Scans the daily holdings of SPY, QQQ, DIA and the 11 Select Sector SPDR ETFs
and lists the stocks that pass your filter criteria.

## Run it (automatic daily download)

1. Put `index.html` and `server.py` in the same folder.
2. Run `python server.py` (Python 3.8+, nothing to install).
3. Your browser opens http://localhost:8000 and all 14 files are fetched and scanned.

Files are cached per day in `./cache/YYYY-MM-DD/`. Use `python server.py 9000` for another port.

## Open it on your phone

### Option A: same Wi-Fi as your computer

1. Run `python server.py --lan`.
2. It prints a line like `On your phone (same Wi-Fi): http://192.168.1.23:8000`.
3. Type that address into your phone's browser. Your computer must stay on.

On Windows, allow Python through the firewall for Private networks when asked.
Only use `--lan` on a network you trust, such as your home Wi-Fi.

### Option B: anywhere, computer off (free GitHub Pages)

GitHub downloads the 14 files every weekday morning and publishes the site with them.

1. Create a free account at github.com and make a new **public** repository (e.g. `stock-scanner`).
2. Upload `index.html`, `server.py` and the `.github` folder (keep the folder path
   `.github/workflows/update-holdings.yml`). Tip: on the upload page, drag the whole
   unzipped folder in so hidden folders are included.
3. In the repo go to **Settings > Pages** and set **Source** to **GitHub Actions**.
4. Go to **Actions > Update holdings > Run workflow** for the first run.
5. Your site is at `https://<your-username>.github.io/stock-scanner/`.

It refreshes every evening at about 7:30, 9:30 and 11:30 pm New York time (one hour earlier in winter); **Run workflow** refreshes on demand.
If a vendor blocks GitHub's download, that fund's tile shows an error and you can drop the file in by hand.

### Add it to your home screen

- iPhone (Safari): Share > Add to Home Screen.
- Android (Chrome): menu > Add to Home screen.

## Run it without the server

Open `index.html` directly. Click each fund tile to download its daily file,
then drop all files onto the page (or use Add files). A `*_Scanners.xlsx`
workbook in the original format also works.

QQQ has no spreadsheet download. Its tile has a Holdings data link: open it,
save the page (Ctrl+S / Cmd+S) as a `.json` file, and drop that in. The site
recognises it as QQQ automatically.

## Where the files come from

| Fund | Daily file |
|---|---|
| SPY, DIA, XLB to XLY | `https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-<ticker>.xlsx` |
| QQQ | The holdings feed behind https://www.invesco.com/qqq-etf/en/about.html: `https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/46090E103/holdings/fund?idType=cusip&productType=ETF` (JSON). Invesco's older CSV download is kept as a fallback. |

sectorspdrs.com now redirects to State Street, which publishes the sector files in the same format as SPY.

## How the scan works

1. Weight column converted to a percentage basis (vendor files show 7.31 for 7.31%).
2. GOOG is merged into GOOGL in every fund (index and sector).
3. Index: keep stocks at or above SPY 0.125%, QQQ 0.5%, DIA 2.5%. Each index must keep 80% of its weight.
4. Sum each stock's kept weights across the three indexes, divide by the grand total (normalized weight), keep 0.5% and above.
5. Sectors: XLF, XLI at least 1.2%; XLK, XLP, XLV, XLY at least 1.5%; XLB, XLC, XLE, XLRE, XLU at least 2%.
   Each sector and the overall total must keep 70% (ideal 75%).

All thresholds can be changed under Adjust thresholds. Export to Excel writes the
Index Final, Index Steps, SPY-QQQ-DIA, Sectors, Sector Stocks, Tabela and Coverage sheets.
