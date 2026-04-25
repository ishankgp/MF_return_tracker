/**
 * Composite score analysis script
 * - Formula A: 70% weight to mean returns, -30% weight to max drawdowns
 * - Formula B: 70% weight to mean returns, -30% weight to difference from max total absolute return
 */

const API_URL = 'http://localhost:5000/api/funds'

async function fetchFundData() {
  const response = await fetch(API_URL)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  const data = await response.json()
  return data.funds || []
}

function computeFundStats(funds, selectedYears) {
  const stats = []

  funds.forEach((fund) => {
    const breakdown = fund.year_breakdown?.['5year']
    if (!breakdown) return

    const selectedYearReturns = []
    for (let year = 1; year <= 5; year++) {
      if (selectedYears.has(year)) {
        const key = `year${year}`
        const yearReturn = breakdown[key]
        if (yearReturn !== undefined && yearReturn !== null) {
          selectedYearReturns.push(yearReturn)
        }
      }
    }

    if (selectedYearReturns.length === 0) return

    const meanReturn =
      selectedYearReturns.reduce((sum, r) => sum + r, 0) /
      selectedYearReturns.length

    // Compute total absolute return across selected years
    const totalMultiplier = selectedYearReturns.reduce(
      (product, r) => product * (1 + r / 100),
      1
    )
    const totalAbsolute = (totalMultiplier - 1) * 100

    // Determine drawdown for full 5Y period if available, fallback to 30%
    let maxDrawdown = breakdown.max_dd_5y ?? 0
    if (!maxDrawdown || maxDrawdown <= 0) {
      maxDrawdown = 30
    }

    stats.push({
      fundName: fund.name,
      meanReturn,
      totalAbsolute,
      maxDrawdown,
    })
  })

  return stats
}

function rankFunds(stats, scoreFn) {
  const results = stats
    .map((stat) => ({
      ...stat,
      score: scoreFn(stat),
    }))
    .sort((a, b) => b.score - a.score)

  return results
}

function printResults(title, results) {
  console.log(`\n${'='.repeat(80)}`)
  console.log(title)
  console.log('='.repeat(80))

  results.forEach((item, index) => {
    const rank = index + 1
    const marker =
      item.fundName.includes('Bandhan') || item.fundName.includes('Motilal')
        ? ' ⭐'
        : ''
    const top3Marker = rank <= 3 ? ' 🏆' : ''

    console.log(
      `${rank.toString().padStart(2)}. ${item.fundName.padEnd(
        45
      )} Score: ${item.score.toFixed(2).padStart(7)} | Mean: ${item.meanReturn
        .toFixed(2)
        .padStart(6)}% | Drawdown: ${item.maxDrawdown
        .toFixed(2)
        .padStart(6)}% | Total Abs: ${item.totalAbsolute
        .toFixed(2)
        .padStart(7)}%${marker}${top3Marker}`
    )
  })
}

async function main() {
  try {
    console.log('Fetching fund data...')
    const funds = await fetchFundData()
    console.log(`Loaded ${funds.length} funds`)

    const selectedYears = new Set([1, 2, 3, 4, 5])
    const stats = computeFundStats(funds, selectedYears)

    if (stats.length === 0) {
      console.error('No fund stats calculated. Exiting.')
      process.exit(1)
    }

    const maxTotalAbsolute = Math.max(...stats.map((s) => s.totalAbsolute))

    // Formula A: 70% return, -30% drawdown
    const resultsCompositeDrawdown = rankFunds(stats, (stat) => {
      return 0.7 * stat.meanReturn - 0.3 * stat.maxDrawdown
    })

    // Formula B: 70% return, -30% difference from max total absolute return
    const resultsCompositeDiff = rankFunds(stats, (stat) => {
      const diffFromMax = maxTotalAbsolute - stat.totalAbsolute
      return 0.7 * stat.meanReturn - 0.3 * diffFromMax
    })

    printResults(
      'Composite Score A: 70% Return, -30% Drawdown',
      resultsCompositeDrawdown
    )
    printResults(
      'Composite Score B: 70% Return, -30% (Max Total Absolute - Fund Total Absolute)',
      resultsCompositeDiff
    )

    // Highlight rankings for Bandhan & Motilal
    const highlight = (results, label) => {
      const bandhanRank =
        results.findIndex((item) => item.fundName.includes('Bandhan')) + 1
      const motilalRank =
        results.findIndex((item) => item.fundName.includes('Motilal')) + 1
      console.log(
        `\n${label} → Bandhan Rank: ${
          bandhanRank || 'N/A'
        }, Motilal Rank: ${motilalRank || 'N/A'}`
      )
    }

    highlight(
      resultsCompositeDrawdown,
      'Composite A (Return vs Drawdown) Rankings'
    )
    highlight(
      resultsCompositeDiff,
      'Composite B (Return vs Gap to Max Total Absolute) Rankings'
    )
  } catch (error) {
    console.error('Error running composite score analysis:', error)
    process.exit(1)
  }
}

main()


