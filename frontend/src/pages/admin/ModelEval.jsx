import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { PageHeader } from "../../components/Feedback";

export default function ModelEval() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/ml/metrics").then((response) => setData(response.data)).catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <div>
      <PageHeader
        title="Complaint classifier"
        subtitle="These figures are read from models/metrics.json, which the training script writes. They are not typed into the page."
      />
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {!data && !error ? <p className="text-sm text-slate-500">Loading metrics…</p> : null}
      {data ? (
        <div className="space-y-4">
          <section className="card p-5 text-sm">
            <p><span className="font-semibold">Dataset:</span> {data.dataset} · {data.rows} rows</p>
            <p><span className="font-semibold">Split:</span> {data.train_size} train / {data.test_size} test, stratified, random state {data.random_state}</p>
            <p><span className="font-semibold">Vectorizer fit:</span> {data.vectorizer_fit_on}</p>
            <p><span className="font-semibold">Deployed:</span> {data.deployed_model}</p>
            <p className="mt-2 text-slate-600">{data.selection_reason}</p>
            <p className="mt-2 text-slate-500">Class counts: {Object.entries(data.class_distribution).map(([name, count]) => `${name} ${count}`).join(" · ")}</p>
          </section>
          <div className="grid gap-4 lg:grid-cols-2">
            {Object.entries(data.models).map(([name, scores]) => (
              <section key={name} className="card p-5">
                <h2 className="font-semibold">{name}</h2>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <Metric label="Accuracy" value={scores.accuracy} />
                  <Metric label="Precision" value={scores.precision_macro} />
                  <Metric label="Recall" value={scores.recall_macro} />
                  <Metric label="Macro F1" value={scores.f1_macro} />
                </dl>
                <div className="mt-4 overflow-x-auto">
                  <table className="text-xs">
                    <thead>
                      <tr>
                        <th className="p-1" />
                        {scores.labels.map((label) => <th key={label} className="p-1 font-medium">{label.slice(0, 4)}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {scores.confusion_matrix.map((row, rowIndex) => (
                        <tr key={scores.labels[rowIndex]}>
                          <th className="p-1 text-left font-medium">{scores.labels[rowIndex]}</th>
                          {row.map((value, column) => (
                            <td key={column} className="p-1 text-center">{value}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-slate-500">Rows are the true category. Columns are the predicted category.</p>
              </section>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-lg font-semibold">{Number(value).toFixed(3)}</dd>
    </div>
  );
}
