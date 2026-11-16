# Baseline model report

TF-IDF (words and two-word phrases) + logistic regression with balanced class weights, predicting the **product**.
Trained 2026-11-16T11:56:29+00:00 on 300,000 complaints from the gold training split.

## Scores

| Split | Complaints | Macro-F1 | Accuracy | Weighted F1 | Dummy macro-F1 |
| --- | --- | --- | --- | --- | --- |
| train | 300,000 | **0.837** | 0.860 | 0.863 | 0.038 |
| validation | 37,903 | **0.715** | 0.808 | 0.818 | 0.041 |
| test | 39,746 | **0.718** | 0.806 | 0.814 | 0.037 |

Macro-F1 gives every product equal weight, so small products count as much as large ones. The dummy model always predicts the most common product and sets the floor.

## Per product (test split)

| Product | Precision | Recall | F1 | Complaints |
| --- | --- | --- | --- | --- |
| Mortgage | 0.934 | 0.942 | 0.938 | 3,012 |
| Student loan | 0.928 | 0.891 | 0.909 | 1,434 |
| Debt collection | 0.932 | 0.821 | 0.873 | 10,153 |
| Vehicle loan or lease | 0.829 | 0.868 | 0.848 | 2,152 |
| Credit card | 0.871 | 0.812 | 0.841 | 7,586 |
| Checking or savings account | 0.831 | 0.771 | 0.800 | 8,329 |
| Money transfer, virtual currency, or money service | 0.679 | 0.739 | 0.708 | 3,535 |
| Payday loan, title loan, personal loan, or advance loan | 0.605 | 0.766 | 0.676 | 1,690 |
| Credit reporting or other personal consumer reports | 0.396 | 0.798 | 0.530 | 913 |
| Prepaid card | 0.377 | 0.640 | 0.475 | 561 |
| Debt or credit management | 0.257 | 0.375 | 0.305 | 381 |

## Confusion matrix (test split)

Rows are the true product, columns the predicted product.

| True \ Predicted | Checking or s… | Credit card | Credit report… | Debt collecti… | Debt or credi… | Money transfe… | Mortgage | Payday loan, … | Prepaid card | Student loan | Vehicle loan … |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Checking or savings account | 6,424 | 390 | 50 | 52 | 33 | 936 | 23 | 81 | 305 | 6 | 29 |
| Credit card | 435 | 6,163 | 226 | 182 | 60 | 138 | 29 | 168 | 141 | 7 | 37 |
| Credit reporting or other perso… | 5 | 35 | 729 | 99 | 12 | 2 | 4 | 11 | 0 | 6 | 10 |
| Debt collection | 66 | 221 | 622 | 8,338 | 235 | 29 | 72 | 311 | 7 | 49 | 203 |
| Debt or credit management | 13 | 26 | 66 | 74 | 143 | 7 | 17 | 19 | 3 | 5 | 8 |
| Money transfer, virtual currenc… | 609 | 82 | 4 | 19 | 18 | 2,611 | 12 | 39 | 125 | 2 | 14 |
| Mortgage | 26 | 16 | 16 | 24 | 6 | 7 | 2,836 | 57 | 2 | 9 | 13 |
| Payday loan, title loan, person… | 54 | 87 | 41 | 54 | 32 | 33 | 16 | 1,294 | 5 | 9 | 65 |
| Prepaid card | 76 | 33 | 1 | 3 | 2 | 77 | 2 | 7 | 359 | 1 | 0 |
| Student loan | 3 | 2 | 37 | 37 | 7 | 3 | 6 | 53 | 2 | 1,277 | 7 |
| Vehicle loan or lease | 20 | 17 | 48 | 61 | 8 | 2 | 21 | 98 | 3 | 5 | 1,869 |

## Words that drive each product

| Product | Top words and phrases |
| --- | --- |
| Checking or savings account | bank, chase, my account, overdraft, checking, deposit, chime, funds, savings, checking account, cd, branch |
| Credit card | card, credit card, synchrony, citi, credit, chase, discover, capital one, barclays, citibank, amex, comenity |
| Credit reporting or other personal consumer reports | experian, equifax, transunion, inquiries, report, credit, inquiry, reporting, with redacted, credit card, accounts, redacted balance |
| Debt collection | debt, collection, collections, owed, owe, bill, credit card, calls, credit, recovery, associates, collector |
| Debt or credit management | credit, debt, experian, debt relief, settlement, bright, lexington, repair, lexington law, services, credit repair, my credit |
| Money transfer, virtual currency, or money service | paypal, zelle, money, coinbase, cashapp, transfer, venmo, wire, funds, transactions, transaction, cash |
| Mortgage | mortgage, escrow, home, heloc, loan, foreclosure, modification, newrez, property, pmi, house, appraisal |
| Payday loan, title loan, personal loan, or advance loan | loan, affirm, personal loan, installment, klarna, loans, line of, finance, acima, onemain, one main, upstart |
| Prepaid card | card, prepaid, netspend, gift, the card, edd, direct express, way2go, cash app, unemployment, cards, gift card |
| Student loan | mohela, nelnet, navient, student, loans, aidvantage, edfinancial, loan, school, forbearance, student loan, education |
| Vehicle loan or lease | car, vehicle, auto, repossession, ally, bridgecrest, auto loan, loan, acceptance, santander, finance, toyota |
