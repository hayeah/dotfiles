import { Route, Switch } from "wouter";
import { Preview } from "./preview/Preview";

export function App() {
  return (
    <Switch>
      <Route path="/preview" component={Preview} />
      <Route>
        <div className="flex h-dvh items-center justify-center text-muted-foreground">
          <div className="space-y-2 text-center">
            <div className="text-lg font-semibold">ptydemo</div>
            <div className="text-sm">
              Visit{" "}
              <a href="/preview" className="underline">
                /preview
              </a>{" "}
              to iterate on the UI with mock data.
            </div>
          </div>
        </div>
      </Route>
    </Switch>
  );
}
