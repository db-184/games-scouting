#!/usr/bin/env node
// Fetches Play Store top chart for a given (country, chart_type, num).
// Output: JSON array of {rank, app_id} to stdout.
// Errors: message to stderr, non-zero exit code.
//
// NOTE: google-play-scraper v10 is ESM-only ("type": "module"),
// so this file uses .mjs extension and ES import syntax instead of require().

import gplay from 'google-play-scraper';

const [country, chartType, numStr] = process.argv.slice(2);
if (!country || !chartType || !numStr) {
  console.error('Usage: fetch_play_chart.mjs <country> <chart_type> <num>');
  process.exit(2);
}
const num = parseInt(numStr, 10);

const collectionMap = {
  top_free: gplay.collection.TOP_FREE,
  top_grossing: gplay.collection.GROSSING,
  top_new: gplay.collection.TOP_FREE, // no dedicated "new" collection — signal logic does the work
};

const collection = collectionMap[chartType];
if (!collection) {
  console.error(`Unknown chart_type: ${chartType}`);
  process.exit(2);
}

gplay
  .list({
    collection: collection,
    category: gplay.category.GAME,
    country: country.toLowerCase(),
    lang: 'en',
    num: num,
  })
  .then((apps) => {
    const ranked = apps.map((a, i) => ({ rank: i + 1, app_id: a.appId }));
    process.stdout.write(JSON.stringify(ranked));
  })
  .catch((err) => {
    console.error(err.message || String(err));
    process.exit(1);
  });
