def evaluate_ranking(test_df, top_k=3):
    results = []

    for date, group in test_df.groupby('date'):
        group = group.sort_values('pred', ascending=False)
        top = group.head(top_k)
        avg_return = top['target'].mean()
        results.append(avg_return)

    return {
        "avg_top_return": sum(results) / len(results),
        "days": len(results)
    }