# Anexo 6 — Ingeniería inversa de mnemo (código)

*Destilado por reasonix flash 2026-08-11 sobre el clon del repo `onemnemo/mnemo` (865K tokens de entrada, $0.0165). Stack analizado: .NET 10 + Avalonia 12 — mnemo está migrando a React+Photino, ver anexo 8.*


## 1. Stack y arquitectura

- **Avalonia 12.0.2** (no 11 como dice el README) + **.NET 10**: `Mnemo.UI/Mnemo.UI.csproj` (`Avalonia` 12.0.2, `net10.0`). Todos los proyectos apuntan a `net10.0` (`Mnemo.Core/Mnemo.Core.csproj:4`).
- **Clean architecture de 4 proyectos** (`MnemoApp.sln`):
  - `Mnemo.Core` — modelos de dominio, interfaces de servicio, enums. Sin dependencias de UI/IO; solo `CommunityToolkit.Mvvm` (`Mnemo.Core.csproj`).
  - `Mnemo.Infrastructure` → referencia a Core. Implementaciones: SQLite (`Microsoft.Data.Sqlite` 10.0.1), FSRS, import/export, packaging, markdown (`Markdig`), PDF (`QuestPDF`).
  - `Mnemo.UI` → referencia Core + Infrastructure (`Mnemo.UI.csproj`). MVVM con `CommunityToolkit.Mvvm` (`[ObservableProperty]`, `ViewModelBase` en `Mnemo.UI/ViewModels/ViewModelBase.cs`), DI con `Microsoft.Extensions.DependencyInjection`.
  - `Mnemo.Infrastructure.Tests` — xUnit sobre Infrastructure.
- **Arranque**: `Program.cs:13-17` (Velopack → `StartWithClassicDesktopLifetime`) → `App.OnFrameworkInitializationCompleted` (`App.axaml.cs:44-121`): `Bootstrapper.Build()` construye el DI, crea `MainWindow` con `MainWindowViewModel`, y cierra con `navService.NavigateTo("overview")` (`App.axaml.cs:118`).
- `Bootstrapper.cs:43-309` es el compositor: registra ~80 servicios, **descubre módulos por reflection** (escanea assemblies `Mnemo.*`, instancia todo `IModule` — `Bootstrapper.cs:320-366`), y luego por cada módulo llama `RegisterRoutes/RegisterSidebarItems/RegisterWidgets` (`Bootstrapper.cs:281-298`).

## 2. Modelo de dominio

**Flashcards** (todo en `Mnemo.Core/Models/Flashcards/`):
- `Flashcard` — contenido puro: `Id, DeckId, Type, Front, Back, Tags, State, IsFlagged, Attachments, SourceInfo, FrontBlocks/BackBlocks` (`Flashcard.cs:11-25`). El cuerpo canónico es `Front`/`Back` (texto/markdown); los bloques son derivados para render rico.
- `FlashcardSchedule` — estado de agenda **1:1 con la tarjeta**: `CardId, DueDate, Stability, Difficulty, Reps, Lapses, FsrsState, LearningStepIndex, LastReviewedAt` (`FlashcardSchedule.cs:7-16`). Ambos se unen en `FlashcardView`.
- `FlashcardFolder` — carpeta jerárquica auto-referencial `Id, Name, ParentId, Order` (`FlashcardFolder.cs:6-10`).
- `FlashcardDeckHeader` — `Id, FolderId, PresetId, Name, Description, Tags, SortOrder, LastStudied` (`FlashcardDeckHeader.cs:8-18`).
- `FlashcardPreset` — perfil de agenda **compartido**: `NewPerDay, MaxReviewsPerDay, Algorithm, DesiredRetention, LearningSteps, RelearnSteps, ShuffleOrder, BuryRelated, AutoReveal, Weights` (`FlashcardPreset.cs:8-22`); default Standard 20/día nuevos, 200 repasos, retención 0.9, pasos [1,10]/[10] (`FlashcardPreset.cs:28-42`).
- `FlashcardCardState` Active/Suspended (`FlashcardCardState.cs:7-11`); `FlashcardType` Classic/Cloze (`FlashcardType.cs:6-10`).

**Notas**: `Note` — `NoteId, Title, FolderId, ParentNoteId, Order, FolderPath, Content (markdown), Blocks, IsFavorite` (`Note.cs:9-64`); `NoteFolder` — `FolderId, Name, ParentId, Order` (`NoteFolder.cs:8-28`). Además hay `MindmapDocument`/`MindmapElement` y modelos de chat.

**Lo importante para multi-tema**: **no existe entidad de tema/materia/curso** — un grep de `Subject|Topic|Course` en Core no arroja ningún modelo de dominio. La separación entre temas se hace con **carpetas jerárquicas + tags** en cada tipo de contenido (`FlashcardDeckHeader.cs:14`). El esquema SQL lo confirma: `FlashcardFolders` auto-referencial, `FlashcardDecks.FolderId` (SET NULL), `FlashcardCards.DeckId` (CASCADE), `FlashcardDecks.PresetId` (`FlashcardStoreSchema.cs:19-70`).

## 3. Motor de repaso

- **FSRS-5, no SM-2, y es el único algoritmo** ("the single scheduling seam — the algorithm resolver is gone", `IFsrsScheduler.cs:6-8`).
- `FsrsScheduler.ApplyGrade(current, grade, reviewedAt, preset)` (`FsrsScheduler.cs:21-117`): máquina de estados New→Learning→Review→Relearning (`FlashcardFsrsState.cs:6-12`) con pasos de minutos del preset (`StepThrough`, `FsrsScheduler.cs:131-156`: Again reinicia al paso 0, Good avanza/gradua, Hard repite, Easy gradua).
- Fórmulas FSRS-5 estándar con **21 pesos configurables por preset**: `NextInterval` (173-179), `Forgetting` (181-186), `RecallStability` (211-222), `ForgetStability` (224-231). Pesos default `FlashcardFsrsParameters.cs:10-17`. Retención clamp 0.70-0.99, `MinStability=0.1` (`FsrsScheduler.cs:17-19`).
- Parámetros expuestos: `DesiredRetention`, `LearningSteps`, `RelearnSteps`, `Weights`, `NewPerDay`, `MaxReviewsPerDay` (preset por deck, `FlashcardPreset.cs`).
- **Los límites diarios se aplican fuera del scheduler**: `FlashcardDueCalculator.Cap` corta nuevos/repasos por presupuesto diario; las cartas en Learning nunca se cortan (`FlashcardDueCalculator.cs:13-22`).
- Preview del intervalo por botón ("10m"/"1d"/"8d") vía `DescribeInterval` (`FsrsScheduler.cs:119-128`). Sesión con contadores New/Learning/Due + progreso (`FlashcardSessionModel.cs:28-31`) y modos Review/Cram/Test (`FlashcardSessionModel.cs:4-9`).

## 4. Sistema de extensión

**Sí, modular por diseño — el contrato es `IModule`** (`Mnemo.Core/Services/IModule.cs:8-33`), 7 puntos de extensión:
1. `ConfigureServices(IServiceRegistrar)` — registrar VMs/servicios en DI
2. `RegisterTranslationSources` — i18n por módulo
3. `RegisterRoutes(INavigationRegistry)` — rutas string→VM (`FlashcardsModule.cs:32-38`)
4. `RegisterSidebarItems(ISidebarService)` — ítems de navegación (`FlashcardsModule.cs:40-50`)
5. `RegisterTools(IFunctionRegistry, IServiceProvider)` — AI tools
6. `RegisterWidgets(IWidgetRegistry, IServiceProvider)` — widgets del dashboard
7. `RegisterKeybindManifest` — atajos declarativos

Los módulos se **descubren por reflection** (`Bootstrapper.cs:320-366`, solo assemblies `Mnemo.*`; comentario en línea 322: "plugin assemblies can be loaded into the AppDomain before discovery"). Hay 11 módulos (`Modules/*/*Module.cs`): CoreUI, Overview, Notes, Flashcards, Chat, Mindmap, Settings, Statistics, Updates, Onboarding. **Un plugin puede añadir: pantallas (rutas+VM+View), sidebar, widgets, AI tools, keybinds, traducciones — pero no tipos de tarjeta nuevos** (el `FlashcardType` es enum cerrado).

Segundo nivel de extensión: **paquetes de datos `.mnemo`** — ZIP con `manifest.json` (format "mnemo-package", versionado, entradas con `PayloadType`+`SchemaVersion`+`Capabilities`, `MnemoPackageManifest.cs:9-61`), manejados por `IMnemoPayloadHandler` por payload type (Notes/Settings/Flashcards/Mindmaps, registrados en `Bootstrapper.cs:142-145`); import con `ImportConflictPolicy` (KeepBoth por defecto, `MnemoPackageContracts.cs:18-29`). Y **adapters de import/export** `IContentFormatAdapter` (`ImportExportCoordinator.cs:10-13`).

## 5. UI y navegación

- **Ventana principal = sidebar + topbar + área única**: `MainWindow.axaml:23-52` — `Border CornerRadius="8"` → Grid `[Sidebar | Topbar / ContentControl]`; el contenido es un solo `ContentControl Content="{Binding Navigation.CurrentViewModel}"` (líneas 34-38) con overlay global arriba (`OverlayPopupHost` ZIndex 10000, línea 49).
- **Navegación por rutas string→ViewModel**: los módulos registran rutas; `NavigationService` (`Mnemo.UI/Services/NavigationService.cs:13-51`) resuelve el VM por DI, mantiene stack de historial + breadcrumbs (`INavigationService.cs:9-20`). `ViewLocator` mapea VM→View. Rutas registradas: `overview, notes, chat, flashcards, flashcard-deck, flashcard-session, flashcard-test, mindmap, mindmap-detail, settings` (`RegisterRoute("` en `Modules/`).
- **Vistas**: `Views/MainWindow.axaml`; por módulo `OverviewView.axaml` (dashboard de widgets), `NotesView.axaml` (editor de bloques), `FlashcardsView/FlashcardDeckView/FlashcardSessionView/FlashcardTestView.axaml`, `ChatView.axaml`, `MindmapView.axaml`, `SettingsView.axaml`, `OnboardingWizardView.axaml` (todo bajo `Modules/*/Views/`).
- **Atajos y command palette: sí.** Sistema de keybinds declarativo por módulo: `global.search` = **Ctrl+K** (abre `GlobalSearchOverlay` — el command palette real, con grupos "Best matches", `Components/Overlays/GlobalSearchOverlay.axaml`), `global.assistant` = Ctrl+J, `global.quick-actions` = **Alt+Shift+Q** (`CoreUIModule.cs:50-110`); editor: Ctrl+B/I/U etc. (`CoreUIModule.cs:147-161`). Soporta conflictos (`KeybindConflictAnalyzer`), overrides persistidos en SQLite y supresión (`KeybindOverrideDocument.cs`, `KeybindSuppressionPolicy.cs`).

## 6. Tipos de contenido

- **Notas**: modelo de bloques tipo Notion — `BlockType`: Text, H1-4, BulletList, NumberedList, Checklist, Quote, Code, Divider, Image, ColumnGroup, TwoColumn, Equation, Page, Sketch (`Blocks.cs:8-27`). `Block` = `Spans` (inline) + `Payload` tipado + `Meta` extensible + `Children` (`Blocks.cs:30-56`). Inline: `TextSpan`, `EquationSpan` (LaTeX atómico), `FractionSpan` (`InlineSpan.cs:14-21`).
- **Flashcards**: texto/markdown en `Front`/`Back` + tipo Cloze + **adjuntos de imagen** (hasta 3 por lado, binario en disco, solo path en DB: `FlashcardAttachment.cs:5-21`).
- **Renderizado**: `MarkdownRenderer.cs` (Markdig); **motor LaTeX propio** (`LaTeXEngine.cs` + `Services/LaTeX/` con layout por cajas: Fraction, Matrix, Sqrt, Script…); syntax highlighting con TextMate (`TextMateSyntaxHighlighter.cs`, catálogo en `CodeLanguageCatalog.cs`); sketch → SVG; mindmaps con nodos de contenido variado (`IElementContent`).
- **Chat**: mensajes con bloques de contenido (tablas, código, imágenes).

## 7. Import/export y persistencia

- **Adaptadores pluggables** (registrados en `Bootstrapper.cs:147-152`): `flashcards.anki` (.apkg, import+export), `flashcards.csv`, `flashcards.mnemo`, `notes.markdown`, `notes.mnemo`, `mindmaps.mnemo`. El coordinador resuelve por `ContentType`+`FormatId` (`ImportExportCoordinator.cs:33-58`).
- **Anki .apkg**: lo abre como ZIP conteniendo SQLite, parsea HTML→markdown, imágenes, cloze `{{c1::…}}` (`FlashcardsAnkiFormatAdapter.cs:16-28, 47-52`).
- **Formato propio `.mnemo`**: ZIP con `manifest.json` + payloads JSON por tipo (`MnemoPackageService.cs:9, 64-84`), con validación de paths anti path-traversal (253-260).
- **Persistencia**: **SQLite local** `%LocalAppData%\Mnemo\mnemo.db` (`MnemoAppPaths.cs:13-20`, `SqliteStorageProvider.cs:22-28`); imágenes en `%LocalAppData%\Mnemo\images\` (`MnemoAppPaths.cs:29-30`). Esquema relacional de flashcards versionado + migrador (`FlashcardStoreMigrator.cs`, `FlashcardStoreSchema.cs:10`).

## 8. Lo robable (decisiones a copiar)

1. **Separar contenido de agenda** — `Flashcard` vs `FlashcardSchedule` 1:1 unidos en `FlashcardView` (`Flashcard.cs:5-9`). Permite reutilizar el motor FSRS para *cualquier* objeto de estudio (capítulos, ejercicios, conceptos), no solo tarjetas.
2. **Carpetas jerárquicas + tags en vez de entidad "materia"** (`FlashcardFolder.cs:6-10`, `FlashcardDeckHeader.cs:14`). Multi-tema sin modelar un taxonomy rígida; el usuario organiza como quiera.
3. **Presets de scheduling compartidos** (deck→preset N:1; "editar un preset cambia todos los decks", `FlashcardPreset.cs:4-7`). Configuración de agenda a nivel global, no por deck.
4. **Scheduler puro + política por fuera** — FSRS-5 sin IO en `FsrsScheduler.cs`; los topes diarios (`NewPerDay/MaxReviewsPerDay`) se aplican en `FlashcardDueCalculator.Cap` (`FlashcardDueCalculator.cs:13-22`). Fácil de testear (tests en `Infrastructure.Tests/Flashcards/`).
5. **Preview de intervalo en el botón de grado** ("10m", "1d", "8d", `FsrsScheduler.cs:119-128`). Reduce la ansiedad de repaso; barato de implementar.
6. **Módulos por convención con discovery por reflection** — `IModule` de 7 hooks (`IModule.cs:8-33`) + `DiscoverModules` (`Bootstrapper.cs:320-366`). Cada feature es un módulo autónomo con sus rutas/sidebar/widgets/keybinds/i18n; la app nueva se construye como colección de módulos.
7. **Command palette gratis gracias al manifest de keybinds** — declarar atajos como datos (`CoreUIModule.cs:50-110`) habilita búsqueda, conflictos detectables y remapeo persistido; la UI (GlobalSearchOverlay, Ctrl+K) sale sola.
8. **Dashboard de widgets registrables** — `IWidgetRegistry` + descriptors (`Modules/Overview/Widgets/*/…WidgetDescriptor.cs`) con layout guardado (`OverviewLayoutStore`). El "home" es composable y cada módulo aporta su widget.
9. **Contenido rico como bloques + markdown como representación canónica portable** — `Block` con `Spans/Payload/Children` (`Blocks.cs:30-56`) y export Markdown (`NotesMarkdownFormatAdapter`) y paquete `.mnemo` versionado por payload (`MnemoPackageManifest.cs:14-20`). Portabilidad y migraciones por schema-version, no por archivo suelto.
10. **Adapters de import/export registrables** — `IContentFormatAdapter` + coordinador por `ContentType/FormatId` (`ImportExportCoordinator.cs:10-31`); añadir Anki/CSV/Markdown fue solo registrar una clase nueva (`Bootstrapper.cs:147-152`).
11. **Una sola ventana con overlays** — todo dialogo/palette/onboarding usa `OverlayPopupHost` (ZIndex 10000, `MainWindow.axaml:49-51`), no ventanas secundarias: consistencia visual y menos gestión de foco. (Estética limpia: borde `CornerRadius=8`, `ExtendClientAreaToDecorationsHint` en `MainWindow.axaml:18-23`.)