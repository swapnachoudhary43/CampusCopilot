# 8. Machine learning guide

## Where the data came from

There is no public complaint dataset bundled with this project. The sentences were written for the project and are stored in `backend/scripts/complaint_corpus.py`. `scripts/train_model.py` exports them to `data/sample_complaints/complaints.csv`.

The CSV columns are:

| Column | Used as a feature? |
| --- | --- |
| id | No |
| text | Yes. This is the only input. |
| category | Yes. This is the label. |
| source | No. It is always `synthetic_project_authored` so nobody mistakes the file for real campus data. |

The training code selects `text` and `category` by name. It does not feed `source` or `id` into TF-IDF. Doing that would be leakage, because `source` is constant and `id` is an arbitrary number.

There are 160 sentences, 20 in each of 8 categories. The set is balanced. `class_weight="balanced"` is still set, but on equal counts it does not change the story. If a future real dataset had 500 infrastructure complaints and 15 library complaints, that setting would increase the penalty for ignoring the small class.

These sentences are not DAVV complaints and not any other university's complaint log. The wording is similar across rows. A score on this file is not a promise about another college's complaints. The measured hold-out scores are in `models/metrics.json`. Do not quote a higher accuracy than that file.

## What the pipeline does

1. Drop duplicate texts. A duplicate could land in both the train and test sides.
2. `train_test_split(..., test_size=0.2, random_state=42, stratify=category)`.
3. Fit `TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)` on the **training texts only**.
4. Transform the test texts with that same vectorizer. Do not call `fit` again.
5. Fit logistic regression and a linear SVM on the training matrix.
6. Score both on the test matrix.
7. Save `models/metrics.json`, `models/deployed.joblib`, and the individual joblib files.

The split for the run recorded in this repository is **128 train and 32 test**. Each class has 4 test sentences. That is small. One mistake moves recall by 0.25. Say that out loud in the viva.

## TF-IDF in one example

The sentence "the campus bus did not arrive" becomes a row of numbers. A word that appears in this sentence but is rare in the training set, such as "bus", gets a larger weight than a word that appears everywhere. A bigram such as "bus route" can be its own feature. The vectorizer's vocabulary is learned from the 128 training sentences. If the test set contains a new word, that word is ignored. It is not added to the vocabulary after the split.

## The two models

**Logistic regression** draws a weighted sum of the TF-IDF features and turns it into a probability with the logistic function. `predict_proba` is what the complaint screen calls confidence. It is the predicted probability of the chosen class, not a guarantee.

**Linear SVM** looks for a straight boundary that separates classes with as wide a margin as possible. It does not naturally output a probability. If it had been deployed, the API would have labelled the score as a softmax of decision margins, not a probability.

Both models used `class_weight="balanced"` and `random_state=42`.

## The numbers from the executed run

These are copied from `models/metrics.json` after `python scripts/train_model.py` on this project. scikit-learn 1.7.2, NumPy 2.2.6.

Both models produced the same test predictions:

| Metric | Logistic regression | Linear SVM |
| --- | --- | --- |
| Accuracy | 0.625 | 0.625 |
| Macro precision | 0.683 | 0.683 |
| Macro recall | 0.625 | 0.625 |
| Macro F1 | 0.624 | 0.624 |

Accuracy is 20 correct out of 32. Macro F1 averages the F1 of each class, so a weak class is not hidden by an easy class.

Per-class F1 for logistic regression (4 test rows each):

| Category | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Infrastructure | 0.25 | 0.25 | 0.25 |
| Hostel | 0.75 | 0.75 | 0.75 |
| Transportation | 1.00 | 1.00 | 1.00 |
| IT Support | 0.80 | 1.00 | 0.89 |
| Library | 0.75 | 0.75 | 0.75 |
| Academic | 0.75 | 0.75 | 0.75 |
| Cleanliness | 1.00 | 0.25 | 0.40 |
| Other | 0.17 | 0.25 | 0.20 |

Transportation is easy because the words "bus" and "route" are distinctive. "Other" is a leftover bucket, so the model confuses it with specific departments. Cleanliness has high precision and low recall: when the model says cleanliness it is usually right, but it misses most cleanliness complaints. Infrastructure is confused with hostel and with other.

The confusion matrix rows are the true class and the columns are the prediction, in the category order above. For logistic regression the row for Infrastructure is `1, 1, 0, 0, 0, 0, 0, 2`. One was correct, one was called hostel, two were called other.

Logistic regression is the deployed model because the macro F1 values were equal and logistic regression can report a probability. That sentence is also stored in `metrics.json` as `selection_reason`.

## How prediction is used

`backend/app/services/ml/predict.py` loads `models/deployed.joblib`. It does not fit anything. Complaint creation still succeeds if the file is missing. The category is then stored as null and the screen says the model was not available.

## Priority is not this model

`backend/app/services/ml/priority.py` checks keywords. "short circuit" is high. "broken" or "cannot" is medium. Otherwise the suggestion is low. The method field is `rule_based`. Do not describe this as a second trained model.

## What would improve it

More real complaints, a larger test set, and a human-labelled priority column collected separately from the keyword list. A better text model might help "Other", but it would not remove the need for a proper test split.
