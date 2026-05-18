import Step, { type StepProps } from "../Step";

export default function ContextStep(props: Omit<StepProps, "title" | "children">) {
  return <Step {...props} title="(stub ContextStep)">stub</Step>;
}
