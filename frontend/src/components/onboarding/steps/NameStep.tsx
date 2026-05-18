import Step, { type StepProps } from "../Step";

export default function NameStep(props: Omit<StepProps, "title" | "children">) {
  return <Step {...props} title="(stub NameStep)">stub</Step>;
}
