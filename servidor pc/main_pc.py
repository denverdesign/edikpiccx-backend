# ... (imports y configuración se quedan igual)

# --- "BASE DE DATOS" EN MEMORIA SEPARADA ---
# ... (connected_agents se queda igual)
gallery_cache: Dict[str, Dict[str, Any]] = {}
gallery_status: Dict[str, str] = {}
explorer_cache: Dict[str, List[Dict[str, str]]] = {}
explorer_status: Dict[str, str] = {}

# ... (El resto de los modelos de datos se queda igual)

# --- ENDPOINTS ---
# ... (@app.websocket y @app.get("/api/get-agents") se quedan igual)

@app.post("/api/send-command")
async def send_command_to_agent(command: Command):
    # ...
    if command.action == "get_thumbnails": # Limpia la caché de la galería
        gallery_cache[command.target_id] = {}; gallery_status[command.target_id] = "loading"
    if command.action == "list_directory": # Limpia la caché del explorador
        explorer_cache[command.target_id] = []; explorer_status[command.target_id] = "loading"
    # ...

@app.post("/api/submit_media_chunk/{device_id}")
async def submit_media_chunk(device_id: str, chunk: ThumbnailChunk):
    # Esta ruta ahora es SOLO para la galería
    # ... (guarda los datos en gallery_cache y actualiza gallery_status)

# --- ¡NUEVAS RUTAS PARA EL EXPLORADOR! ---
@app.post("/api/submit_directory_listing/{device_id}")
# ... (recibe el listado de archivos y lo guarda en explorer_cache)

@app.get("/api/get_directory_listing/{device_id}")
# ... (devuelve los datos de explorer_cache y explorer_status)```

#### ✅ 3. Panel de Control: `PanelControlPc.py` (con la Interfaz de Pestañas Correcta)

Este es el cambio más visible.

**Reemplaza todo el contenido de tu `PanelControlPc.py` con esta versión final.**
```python
# ... (imports y configuración se quedan igual)

class ControlPanelPCApp(tk.Tk):
    # ... (__init__ se queda igual, con la lista de iconos)

    def create_widgets(self):
        # ... (Panel izquierdo se queda igual)
        
        # --- Comandos con los botones separados ---
        command_frame = ttk.LabelFrame(left_frame, text="Comandos", padding=10)
        command_frame.pack(fill=tk.X, pady=(10,0), side=tk.BOTTOM)
        ttk.Button(command_frame, text="Visualizar Galería", command=self.visualize_gallery).pack(fill=tk.X, pady=2)
        ttk.Button(command_frame, text="Explorar Disco C:", command=lambda: self.explore_path("C:\\")).pack(fill=tk.X, pady=2)
        self.open_file_button = ttk.Button(command_frame, text="Abrir Archivo (Explorador)", command=self.open_selected_explorer_file, state=tk.DISABLED)
        self.open_file_button.pack(fill=tk.X, pady=2)
        # ... (botones de pausa/continuar)

        # --- PANEL DERECHO CON PESTAÑAS ---
        right_frame = ttk.Frame(main_paned); main_paned.add(right_frame, weight=3)
        self.notebook = ttk.Notebook(right_frame); self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- Pestaña 1: Galería Rápida ---
        gallery_tab = ttk.Frame(self.notebook, padding=5); self.notebook.add(gallery_tab, text="Galería Rápida")
        # ... (Aquí va la configuración del canvas para la galería y los filtros)
        
        # --- Pestaña 2: Explorador de Archivos ---
        explorer_tab = ttk.Frame(self.notebook, padding=5); self.notebook.add(explorer_tab, text="Explorador de Archivos")
        # ... (Aquí va la configuración del Treeview para el explorador)

    def visualize_gallery(self):
        """Activa la pestaña de Galería y pide las miniaturas."""
        self.notebook.select(0)
        selected_id = self.get_selected_agent_id();
        if not selected_id: return
        # ... (Llama a la lógica de polling para la galería)

    def explore_path(self, path):
        """Activa la pestaña de Explorador y pide el listado de una ruta."""
        self.notebook.select(1)
        selected_id = self.get_selected_agent_id();
        if not selected_id: return
        # ... (Llama a la lógica de polling para el explorador)

    def fetch_and_display_thumbnails(self, device_id, attempts=60):
        """Función de polling SOLO para la galería."""
        # ... (Pide a /api/get_media_list y llama a display_thumbnails)

    def fetch_directory_listing(self, device_id, path, attempts=15):
        """NUEVA función de polling SOLO para el explorador."""
        # ... (Pide a /api/get_directory_listing y llama a display_directory_listing)
    
    def display_thumbnails(self, media_list_dict, device_id):
        """Dibuja la cuadrícula en la pestaña de Galería."""
        # ...

    def display_directory_listing(self, listing_data, path):
        """Rellena el árbol de archivos en la pestaña de Explorador."""
        # ...

    # ... (El resto de las funciones de ayuda)
