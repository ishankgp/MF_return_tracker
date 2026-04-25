import asyncio
import pandas as pd
from fetch_mf_returns import fetch_all_funds_async

async def main():
    print("Fetching fund data...")
    results = await fetch_all_funds_async()
    
    if not results:
        print("No data fetched.")
        return

    funds_data = []
    for r in results:
        if not r: continue
        # Extract returns, defaulting to 0 if missing/error
        r1y = r['returns'].get('1year', 0)
        r2y = r['returns'].get('2year', 0)
        r3y = r['returns'].get('3year', 0)
        
        # Ensure they are numbers (handle errors if stored as strings or None)
        try: r1y = float(r1y) 
        except: r1y = 0
        try: r2y = float(r2y) 
        except: r2y = 0
        try: r3y = float(r3y) 
        except: r3y = 0

        # Strategy 1: 3-Year CAGR
        score_3y = r3y

        # Strategy 2: Weighted Consistency (User Suggestion)
        # "consistently doing well in 1,2and 3 year data longer the timeframe slightly higher the weightage"
        # Weights: 1Y=20%, 2Y=30%, 3Y=50%
        score_weighted = (r1y * 0.2) + (r2y * 0.3) + (r3y * 0.5)

        funds_data.append({
            "Name": r['name'],
            "1Y": r1y,
            "2Y": r2y,
            "3Y": r3y,
            "Score_3Y": score_3y,
            "Score_Weighted": score_weighted
        })

    df = pd.DataFrame(funds_data)

    # Rank by 3Y
    df['Rank_3Y'] = df['Score_3Y'].rank(ascending=False)
    
    # Rank by Weighted
    df['Rank_Weighted'] = df['Score_Weighted'].rank(ascending=False)

    # Display comparison
    print("\nRanking Comparison:")
    print("=" * 100)
    # Sort by Weighted Rank for display
    df_sorted = df.sort_values('Rank_Weighted')
    
    print(df_sorted[['Name', '1Y', '2Y', '3Y', 'Rank_3Y', 'Rank_Weighted']].to_string(index=False))

    print("\n")
    print("Correlation between rankings:")
    print(df[['Rank_3Y', 'Rank_Weighted']].corr())

    # Check for differences
    diffs = df[df['Rank_3Y'] != df['Rank_Weighted']]
    if not diffs.empty:
        print("\nFunds with different rankings:")
        print(diffs[['Name', 'Rank_3Y', 'Rank_Weighted']].to_string(index=False))
    else:
        print("\nRankings are identical.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
