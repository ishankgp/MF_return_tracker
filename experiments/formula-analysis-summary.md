# Consistency Score Formula Analysis & Recommendations

## Test Results Summary

After testing 13 different formulas, **no single formula puts both Bandhan Small Cap and Motilal Midcap in the top 3**.

### Key Findings

**Fund Metrics (5-year period):**
- **Quant Small Cap**: 40.29% return, 25.17% drawdown
- **Motilal Midcap**: 35.72% return, 24.33% drawdown  
- **Bandhan Small Cap**: 35.34% return, 24.34% drawdown
- **Nippon Small Cap**: 36.09% return, 24.21% drawdown
- **Edelweiss Mid Cap**: 32.11% return, 20.06% drawdown
- **Nippon Growth**: 31.39% return, 19.87% drawdown

**The Challenge:**
- Quant has **5% higher return** than Bandhan/Motilal with similar drawdown (~25%)
- Edelweiss/Nippon Growth have **4-5% lower drawdown** than Bandhan/Motilal but lower returns

## Best Performing Formulas

### Option 1: Simple Return-to-Drawdown Ratio
**Formula:** `Return ÷ Drawdown`

### ✅ Option 2: Square Root Drawdown Penalty
**Formula:** `Return ÷ √Drawdown`

**Rankings:**
1. Quant Small Cap (100)
2. Nippon India Small Cap (70)
3. **Motilal Midcap (66)** ⭐
4. **Bandhan Small Cap (63)** ⭐ (4th place - close!)
5. Edelweiss Mid Cap (63)

**Analysis:** Motilal is in top 3, Bandhan is 4th (only 3 points behind Edelweiss). This is the closest we get to both in top 3.

### ✅ Option 5: Multiplicative Penalty
**Formula:** `Return × (1 - Drawdown/100)`

**Rankings:**
1. Quant Small Cap (100)
2. Nippon India Small Cap (73)
3. **Motilal Midcap (70)** ⭐
4. **Bandhan Small Cap (67)** ⭐ (4th place)
5. Edelweiss Mid Cap (57)

**Analysis:** Similar to Option 2 - Motilal in top 3, Bandhan close behind in 4th.

### Composite A: 70% Return − 30% Max Drawdown
**Formula:** `Score = (0.7 × Mean Return) − (0.3 × Max Drawdown)`

**Rankings (scores in raw units):**
1. Quant Small Cap — 20.65  
2. Nippon India Small Cap — 18.00  
3. **Motilal Midcap — 17.71** ⭐  
4. **Bandhan Small Cap — 17.44** ⭐  
5. Edelweiss Mid Cap — 16.46

**Analysis:** This exactly matches the new “70/30 returns vs drawdown” request. Motilal makes the podium, Bandhan ends up a razor-thin 0.27 points behind Motilal, so it still lands 4th.

### Composite B: 70% Return − 30% (Gap to Max Total Absolute Return)
**Formula:** `Score = (0.7 × Mean Return) − 0.3 × (Max Total Abs − Fund Total Abs)`  
*(Total Absolute calculated from compounded multi-year returns; the max gap is measured against Quant’s +342.44% 5Y absolute return.)*

**Rankings (scores in raw units):**
1. Quant Small Cap — 28.20  
2. **Motilal Midcap — 16.30** ⭐  
3. Nippon India Small Cap — 14.26  
4. **Bandhan Small Cap — 11.17** ⭐  
5. Edelweiss Mid Cap — −0.22

**Analysis:** Penalising the distance from the top total absolute return still keeps Quant far ahead (because all gaps are measured against it). Motilal ranks #2 thanks to its high absolute return (313%), while Bandhan (297%) remains #4.

## Why No Formula Works Perfectly

1. **Quant's dominance**: 40.29% return is significantly higher than others (35-36%), making it hard to dethrone
2. **Bandhan/Motilal similarity**: They have nearly identical metrics (35.34% vs 35.72% return, 24.34% vs 24.33% drawdown)
3. **Trade-off problem**: 
   - Formulas that favor returns → Quant wins
   - Formulas that heavily penalize drawdowns → Edelweiss/Nippon Growth win
   - Sweet spot formulas → Motilal gets in, but Bandhan is just outside

## Recommendations

### Option A: Use Option 2 (Square Root Drawdown) - RECOMMENDED
**Formula:** `Return ÷ √Drawdown`

**Pros:**
- Motilal is in top 3
- Bandhan is very close (4th, only 3 points from 3rd)
- Balanced approach that moderately penalizes drawdowns
- Industry-recognized pattern (similar to Sharpe ratio concept)

**Cons:**
- Bandhan is not technically in top 3 (but very close)

### Option B: Use Option 5 (Multiplicative Penalty)
**Formula:** `Return × (1 - Drawdown/100)`

**Pros:**
- Motilal is in top 3
- Intuitive formula (net return after accounting for worst-case loss)
- Bandhan is close (4th place)

**Cons:**
- Bandhan is not technically in top 3

### Option C: Hybrid Approach
Create a custom formula that combines elements:
- Use Option 2 as base
- Add a small bonus for funds with returns between 35-36% and drawdowns between 24-25%
- This would push Bandhan into top 3

**Example:** `(Return ÷ √Drawdown) × (1 + consistencyBonus)`

### Option D: Accept Current Ranking
If the goal is to identify the "most consistent" funds, Option 2's ranking might actually be correct:
- Quant has highest return with reasonable drawdown
- Motilal has good return with slightly better drawdown than Quant
- Bandhan is very similar to Motilal (essentially tied)

## Implementation Recommendation

**I recommend Option 2: Square Root Drawdown Penalty**

**Formula:** `Score = Mean Return ÷ √Max Drawdown`

**Rationale:**
1. Motilal is in top 3 ✅
2. Bandhan is extremely close (4th, only 3 normalized points behind)
3. The formula is mathematically sound and interpretable
4. It balances return reward with drawdown penalty appropriately
5. The difference between Bandhan (4th) and Edelweiss (5th) is minimal (63 vs 63), suggesting they're essentially tied

**If Bandhan must be in top 3**, consider Option C (hybrid with consistency bonus) or accept that the data shows Motilal and Bandhan are essentially equivalent performers.

## Next Steps

1. Implement Option 2 (Square Root Drawdown)
2. Test with user to see if 4th place for Bandhan is acceptable
3. If not, implement Option C (hybrid with bonus)
4. Consider adding a "tie-breaker" metric (e.g., lower volatility) for funds with very similar scores

