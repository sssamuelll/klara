import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CardOut, ModulePathItem, StoryListItem } from "../api/types";
import { buildCourseVM, type CourseVM } from "./courseView";

export function useCourseData(): { vm: CourseVM } {
  const [vm, setVm] = useState<CourseVM>(() =>
    buildCourseVM({ modules: null, due: null, latestStoryId: null })
  );
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [modules, due, stories] = await Promise.all([
        api.listModules().catch(() => null),
        // ponytail: el 50 es explícito — el default del cliente es 20 y capa el badge.
        api.dueCards(50).catch(() => null),
        api.listStories(1, 0).catch(() => [] as StoryListItem[]),
      ]);
      if (cancelled) return;
      setVm(
        buildCourseVM({
          modules: modules as ModulePathItem[] | null,
          due: due as CardOut[] | null,
          latestStoryId: stories[0]?.id ?? null,
        })
      );
    })();
    return () => { cancelled = true; };
  }, []);
  return { vm };
}
