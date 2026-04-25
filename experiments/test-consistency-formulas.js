/**
 * Test script to evaluate different consistency score formulas
 * Tests all formulas and shows which ones rank Bandhan Small Cap and Motilal Midcap in top 3
 */

const API_URL = 'http://localhost:5000/api/funds';

// All formula options to test
const FORMULAS = {
  'Current (Return^1.5 ÷ Drawdown)': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.5) / worstDrawdown;
  },
  'Option 1: Calmar Ratio (Linear)': (meanReturn, worstDrawdown) => {
    return meanReturn / worstDrawdown;
  },
  'Option 2: Square Root Drawdown': (meanReturn, worstDrawdown) => {
    return meanReturn / Math.sqrt(worstDrawdown);
  },
  'Option 3: Return Minus Drawdown': (meanReturn, worstDrawdown) => {
    return meanReturn - worstDrawdown;
  },
  'Option 4: Squared Drawdown Penalty': (meanReturn, worstDrawdown) => {
    return meanReturn / (worstDrawdown * worstDrawdown);
  },
  'Option 5: Multiplicative Penalty': (meanReturn, worstDrawdown) => {
    return meanReturn * (1 - worstDrawdown / 100);
  },
  'Option 6: Hybrid (Return^1.2 ÷ Drawdown^1.5)': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.2) / Math.pow(worstDrawdown, 1.5);
  },
  'Option 7: Return ÷ Drawdown^1.3': (meanReturn, worstDrawdown) => {
    return meanReturn / Math.pow(worstDrawdown, 1.3);
  },
  'Option 8: Return^1.1 ÷ Drawdown^1.2': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.1) / Math.pow(worstDrawdown, 1.2);
  },
  'Option 9: Return ÷ Drawdown^1.05': (meanReturn, worstDrawdown) => {
    return meanReturn / Math.pow(worstDrawdown, 1.05);
  },
  'Option 10: Return^1.15 ÷ Drawdown^1.25': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.15) / Math.pow(worstDrawdown, 1.25);
  },
  'Option 11: Return^1.25 ÷ Drawdown^1.35': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.25) / Math.pow(worstDrawdown, 1.35);
  },
  'Option 12: Return^1.35 ÷ Drawdown^1.45': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.35) / Math.pow(worstDrawdown, 1.45);
  },
  'Option 13: Return^1.05 ÷ Drawdown^1.15': (meanReturn, worstDrawdown) => {
    return Math.pow(meanReturn, 1.05) / Math.pow(worstDrawdown, 1.15);
  },
  'Weighted 1: 70% Return - 30% Drawdown': (meanReturn, worstDrawdown) => {
    // Normalize: return can be 0-100, drawdown can be 0-100
    // Score = 0.7 * return - 0.3 * drawdown
    return (0.7 * meanReturn) - (0.3 * worstDrawdown);
  },
  'Weighted 2: 60% Return - 40% Drawdown': (meanReturn, worstDrawdown) => {
    return (0.6 * meanReturn) - (0.4 * worstDrawdown);
  },
  'Weighted 3: 80% Return - 20% Drawdown': (meanReturn, worstDrawdown) => {
    return (0.8 * meanReturn) - (0.2 * worstDrawdown);
  },
  'Weighted 4: 75% Return - 25% Drawdown': (meanReturn, worstDrawdown) => {
    return (0.75 * meanReturn) - (0.25 * worstDrawdown);
  },
  'Weighted 5: 65% Return - 35% Drawdown': (meanReturn, worstDrawdown) => {
    return (0.65 * meanReturn) - (0.35 * worstDrawdown);
  },
};

function calculateStdDev(values) {
  if (values.length === 0) return 0;
  const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
  const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
  return Math.sqrt(variance);
}

function normalizeScores(scoreData) {
  if (scoreData.length === 0) return [];
  
  const scores = scoreData.map(sd => sd.rawScore);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const range = maxScore - minScore;
  
  return scoreData.map(sd => {
    let normalizedScore;
    if (range === 0) {
      normalizedScore = 50;
    } else {
      normalizedScore = ((sd.rawScore - minScore) / range) * 100;
    }
    return {
      ...sd,
      normalizedScore: Math.round(normalizedScore)
    };
  });
}

function calculateScores(funds, selectedYears, formulaFn, formulaName, isWeightedComposite = false) {
  const scoreData = [];
  
  // For weighted composite, we need to collect all data first for normalization
  const tempData = [];
  
  funds.forEach(fund => {
    const breakdown = fund.year_breakdown?.["5year"];
    if (!breakdown) return;
    
    // Extract individual year returns for selected years only
    const selectedYearReturns = [];
    for (let year = 1; year <= 5; year++) {
      if (selectedYears.has(year)) {
        const key = `year${year}`;
        const yearReturn = breakdown[key];
        if (yearReturn !== undefined && yearReturn !== null) {
          selectedYearReturns.push(yearReturn);
        }
      }
    }
    
    if (selectedYearReturns.length === 0) return;
    
    // Calculate mean return
    const meanReturn = selectedYearReturns.reduce((sum, r) => sum + r, 0) / selectedYearReturns.length;
    
    // Determine which full-period max drawdown to use
    let worstDrawdown = 0;
    const selectedYearsArray = Array.from(selectedYears).sort();
    
    if (selectedYearsArray.length === 2 && selectedYearsArray[0] === 4 && selectedYearsArray[1] === 5) {
      worstDrawdown = breakdown.max_dd_2y ?? 0;
    } else if (selectedYearsArray.length === 3 && selectedYearsArray[0] === 3 && selectedYearsArray[1] === 4 && selectedYearsArray[2] === 5) {
      worstDrawdown = breakdown.max_dd_3y ?? 0;
    } else if (selectedYearsArray.length === 5 && selectedYearsArray.every((y, i) => y === i + 1)) {
      worstDrawdown = breakdown.max_dd_5y ?? 0;
    } else {
      const selectedYearMaxDrawdowns = [];
      for (let year = 1; year <= 5; year++) {
        if (selectedYears.has(year)) {
          const ddKey = `year${year}_max_dd`;
          const maxDD = breakdown[ddKey];
          if (maxDD !== undefined && maxDD !== null && maxDD > 0) {
            selectedYearMaxDrawdowns.push(maxDD);
          }
        }
      }
      worstDrawdown = selectedYearMaxDrawdowns.length > 0 ? Math.max(...selectedYearMaxDrawdowns) : 0;
    }
    
    // Use conservative default if drawdown is 0 or missing
    if (worstDrawdown === 0 || worstDrawdown === null || worstDrawdown === undefined) {
      worstDrawdown = 30;
    }
    
    tempData.push({
      fundName: fund.name,
      meanReturn,
      maxDrawdown: worstDrawdown,
      stdDev: calculateStdDev(selectedYearReturns)
    });
  });
  
  if (tempData.length === 0) return [];
  
  // Calculate raw scores
  if (isWeightedComposite) {
    // For weighted composite, normalize first then apply weights
    const returns = tempData.map(d => d.meanReturn);
    const drawdowns = tempData.map(d => d.maxDrawdown);
    
    const minReturn = Math.min(...returns);
    const maxReturn = Math.max(...returns);
    const returnRange = maxReturn - minReturn;
    
    const minDrawdown = Math.min(...drawdowns);
    const maxDrawdown = Math.max(...drawdowns);
    const drawdownRange = maxDrawdown - minDrawdown;
    
    tempData.forEach(data => {
      // Normalize return (0-100, higher is better)
      const normalizedReturn = returnRange === 0 ? 50 : ((data.meanReturn - minReturn) / returnRange) * 100;
      
      // Normalize drawdown (0-100, lower drawdown = higher score)
      const normalizedDrawdown = drawdownRange === 0 ? 50 : ((data.maxDrawdown - minDrawdown) / drawdownRange) * 100;
      
      // Calculate weighted composite
      const rawScore = formulaFn(normalizedReturn, normalizedDrawdown, data.meanReturn, maxReturn);
      
      scoreData.push({
        fundName: data.fundName,
        rawScore,
        meanReturn: data.meanReturn,
        maxDrawdown: data.maxDrawdown,
        stdDev: data.stdDev
      });
    });
  } else {
    // Original formula-based calculation
    tempData.forEach(data => {
      const rawScore = formulaFn(data.meanReturn, data.maxDrawdown);
      
      scoreData.push({
        fundName: data.fundName,
        rawScore,
        meanReturn: data.meanReturn,
        maxDrawdown: data.maxDrawdown,
        stdDev: data.stdDev
      });
    });
  }
  
  // Normalize scores
  const normalized = normalizeScores(scoreData);
  
  // Sort by normalized score (descending)
  normalized.sort((a, b) => b.normalizedScore - a.normalizedScore);
  
  return normalized;
}

function printRankings(formulaName, rankings) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`FORMULA: ${formulaName}`);
  console.log('='.repeat(80));
  
  rankings.forEach((item, index) => {
    const rank = index + 1;
    const isBandhan = item.fundName.includes('Bandhan');
    const isMotilal = item.fundName.includes('Motilal');
    const marker = (isBandhan || isMotilal) ? ' ⭐' : '';
    const top3Marker = rank <= 3 ? ' 🏆' : '';
    
    console.log(
      `${rank.toString().padStart(2)}. ${item.fundName.padEnd(45)} ` +
      `Score: ${item.normalizedScore.toString().padStart(3)} ` +
      `(Raw: ${item.rawScore.toFixed(2)}, ` +
      `Return: ${item.meanReturn.toFixed(2)}%, ` +
      `DD: ${item.maxDrawdown.toFixed(2)}%)${marker}${top3Marker}`
    );
  });
  
  // Check if Bandhan and Motilal are in top 3
  const top3 = rankings.slice(0, 3).map(r => r.fundName);
  const bandhanInTop3 = top3.some(name => name.includes('Bandhan'));
  const motilalInTop3 = top3.some(name => name.includes('Motilal'));
  
  if (bandhanInTop3 && motilalInTop3) {
    console.log('\n✅ SUCCESS: Both Bandhan Small Cap and Motilal Midcap are in TOP 3!');
  } else if (bandhanInTop3) {
    console.log('\n⚠️  PARTIAL: Bandhan Small Cap is in top 3, but Motilal Midcap is not');
  } else if (motilalInTop3) {
    console.log('\n⚠️  PARTIAL: Motilal Midcap is in top 3, but Bandhan Small Cap is not');
  } else {
    console.log('\n❌ Neither Bandhan Small Cap nor Motilal Midcap are in top 3');
  }
}

async function main() {
  console.log('Fetching fund data from API...');
  
  try {
    const response = await fetch(API_URL);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    const funds = data.funds || [];
    
    if (funds.length === 0) {
      console.error('No funds data received. Make sure the Flask backend is running on port 5000.');
      process.exit(1);
    }
    
    console.log(`\nLoaded ${funds.length} funds`);
    console.log('\nTesting all formulas with all 5 years selected...\n');
    
    // Test with all 5 years selected
    const selectedYears = new Set([1, 2, 3, 4, 5]);
    
    const allResults = {};
    const successfulFormulas = [];
    
    // Test each formula
    for (const [formulaName, formulaFn] of Object.entries(FORMULAS)) {
      const rankings = calculateScores(funds, selectedYears, formulaFn, formulaName, false);
      allResults[formulaName] = rankings;
      printRankings(formulaName, rankings);
      
      // Check if both are in top 3
      const top3 = rankings.slice(0, 3).map(r => r.fundName);
      const bandhanInTop3 = top3.some(name => name.includes('Bandhan'));
      const motilalInTop3 = top3.some(name => name.includes('Motilal'));
      
      if (bandhanInTop3 && motilalInTop3) {
        successfulFormulas.push(formulaName);
      }
    }
    
    // Test weighted composite formulas
    console.log('\n\n' + '='.repeat(80));
    console.log('TESTING WEIGHTED COMPOSITE FORMULAS');
    console.log('='.repeat(80));
    
    for (const [formulaName, formulaFn] of Object.entries(WEIGHTED_FORMULAS)) {
      const rankings = calculateScores(funds, selectedYears, formulaFn, formulaName, true);
      allResults[formulaName] = rankings;
      printRankings(formulaName, rankings);
      
      // Check if both are in top 3
      const top3 = rankings.slice(0, 3).map(r => r.fundName);
      const bandhanInTop3 = top3.some(name => name.includes('Bandhan'));
      const motilalInTop3 = top3.some(name => name.includes('Motilal'));
      
      if (bandhanInTop3 && motilalInTop3) {
        successfulFormulas.push(formulaName);
      }
    }
    
    // Summary
    console.log(`\n${'='.repeat(80)}`);
    console.log('SUMMARY');
    console.log('='.repeat(80));
    
    if (successfulFormulas.length > 0) {
      console.log('\n✅ FORMULAS THAT PUT BOTH BANDHAN AND MOTILAL IN TOP 3:');
      successfulFormulas.forEach((name, index) => {
        console.log(`   ${index + 1}. ${name}`);
      });
    } else {
      console.log('\n❌ No formula puts both Bandhan Small Cap and Motilal Midcap in top 3');
      console.log('\nLet me check individual rankings...\n');
      
      // Check which formulas have Bandhan in top 3
      const bandhanFormulas = [];
      const motilalFormulas = [];
      
      for (const [formulaName, rankings] of Object.entries(allResults)) {
        const top3 = rankings.slice(0, 3).map(r => r.fundName);
        if (top3.some(name => name.includes('Bandhan'))) {
          bandhanFormulas.push(formulaName);
        }
        if (top3.some(name => name.includes('Motilal'))) {
          motilalFormulas.push(formulaName);
        }
      }
      
      if (bandhanFormulas.length > 0) {
        console.log('Formulas with Bandhan Small Cap in top 3:');
        bandhanFormulas.forEach(name => console.log(`  - ${name}`));
      }
      
      if (motilalFormulas.length > 0) {
        console.log('\nFormulas with Motilal Midcap in top 3:');
        motilalFormulas.forEach(name => console.log(`  - ${name}`));
      }
    }
    
    // Recommendation
    console.log(`\n${'='.repeat(80)}`);
    console.log('RECOMMENDATION');
    console.log('='.repeat(80));
    
    if (successfulFormulas.length > 0) {
      const recommended = successfulFormulas[0];
      console.log(`\n🎯 RECOMMENDED: ${recommended}`);
      console.log('\nThis formula successfully ranks both Bandhan Small Cap and Motilal Midcap in the top 3.');
      
      // Show detailed breakdown of recommended formula
      const recRankings = allResults[recommended];
      console.log('\nDetailed breakdown:');
      recRankings.slice(0, 5).forEach((item, index) => {
        console.log(`\n${index + 1}. ${item.fundName}`);
        console.log(`   Normalized Score: ${item.normalizedScore}`);
        console.log(`   Raw Score: ${item.rawScore.toFixed(4)}`);
        console.log(`   Mean Return: ${item.meanReturn.toFixed(2)}%`);
        console.log(`   Max Drawdown: ${item.maxDrawdown.toFixed(2)}%`);
        console.log(`   Std Deviation: ${item.stdDev.toFixed(2)}%`);
      });
    } else {
      console.log('\n⚠️  No single formula achieves both goals.');
      console.log('Consider:');
      console.log('1. Using a formula that heavily penalizes drawdowns (Options 4, 6, 7, 8)');
      console.log('2. Checking if Bandhan/Motilal have significantly lower drawdowns than Quant');
      console.log('3. Using a hybrid approach or weighted combination');
    }
    
  } catch (error) {
    console.error('Error:', error.message);
    console.error('\nMake sure:');
    console.error('1. Flask backend is running on http://localhost:5000');
    console.error('2. You have run: python app.py');
    process.exit(1);
  }
}

// Run the test
main().catch(console.error);

