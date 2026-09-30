/* Generated from raylib C signatures by recording.py; do not edit. */
enum { OP_BeginTextureMode=1, OP_EndTextureMode=2, OP_BeginShaderMode=3, OP_EndShaderMode=4, OP_BeginBlendMode=5, OP_EndBlendMode=6, OP_ClearBackground=7, OP_BeginScissorMode=8, OP_EndScissorMode=9, OP_DrawTexture=10, OP_DrawTextureRec=11, OP_DrawTexturePro=12, OP_DrawTextureEx=13, OP_DrawRectangle=14, OP_DrawRectangleRec=15, OP_DrawRectanglePro=16, OP_DrawRectangleLines=17, OP_DrawRectangleLinesEx=18, OP_DrawCircle=19, OP_DrawCircleV=20, OP_DrawCircleGradient=21, OP_DrawEllipse=22, OP_DrawLine=23, OP_DrawLineV=24, OP_DrawLineEx=25, OP_DrawTriangle=26, OP_DrawPixel=27, OP_DrawPixelV=28, OP_DrawText=29, OP_DrawTextEx=30, OP_SetTextureFilter=31, OP_SetTextureWrap=32, OP_rlBegin=33, OP_rlEnd=34, OP_rlColor4ub=35, OP_rlNormal3f=36, OP_rlTexCoord2f=37, OP_rlVertex2f=38, OP_rlVertex3f=39, OP_rlPushMatrix=40, OP_rlPopMatrix=41, OP_rlTranslatef=42, OP_rlScalef=43, OP_rlRotatef=44, OP_rlDisableBackfaceCulling=45, OP_rlEnableBackfaceCulling=46, OP_rlDrawRenderBatchActive=47, OP_rlSetBlendFactors=48, OP_rlSetBlendFactorsSeparate=49, OP_LoadTexture=50, OP_LoadTextureFromImage=51, OP_LoadRenderTexture=52, OP_LoadShader=53, OP_LoadShaderFromMemory=54, OP_GetShaderLocation=55, OP_SetShaderValue=56, OP_SetShaderValueV=57, OP_SetShaderValueTexture=58, OP_UnloadTexture=59, OP_UnloadRenderTexture=60, OP_UnloadShader=61, OP_UpdateTexture=62, OP_UploadMesh=63, OP_DrawMesh=64, OP_UnloadMesh=65, OP_UpdateMeshBuffer=66, OP_rlSetTexture=67, OP_DrawTriangleFan=68, OP_DrawTriangleStrip=69, OP_HFTexture=70, OP_HFTarget=71, OP_HFShader=72, OP_HFLocation=73, OP_HFUniform=74, OP_HFSampler=75, OP_HFFont=76, OP_HFGrid=77, OP_HFRay=78, OP_HFSceneGeometry=79, OP_HFVisibility=80, OP_HFVisibilityFan=81, OP_HFTreeDefinition=82, OP_HFTreePose=83, OP_HFTreeUniform=84, OP_HFTreeAngle=85 };
static Color rd_Color(Reader *r) { Color v;v.r=rd_i32(r);v.g=rd_i32(r);v.b=rd_i32(r);v.a=rd_i32(r);return v; }
static Rectangle rd_Rectangle(Reader *r) { Rectangle v;v.x=rd_float(r);v.y=rd_float(r);v.width=rd_float(r);v.height=rd_float(r);return v; }
static Vector2 rd_Vector2(Reader *r) { Vector2 v;v.x=rd_float(r);v.y=rd_float(r);return v; }
#define HF_SIMPLE_CASES case OP_BeginTextureMode: { struct RenderTexture a0=targets[rd_id(r)];BeginTextureMode(a0);break; } \
case OP_EndTextureMode: { EndTextureMode();break; } \
case OP_BeginShaderMode: { struct Shader a0=shaders[rd_id(r)];BeginShaderMode(a0);break; } \
case OP_EndShaderMode: { EndShaderMode();break; } \
case OP_BeginBlendMode: { int a0=rd_i32(r);BeginBlendMode(a0);break; } \
case OP_EndBlendMode: { EndBlendMode();break; } \
case OP_ClearBackground: { struct Color a0=rd_Color(r);ClearBackground(a0);break; } \
case OP_BeginScissorMode: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);BeginScissorMode(a0,a1,a2,a3);break; } \
case OP_EndScissorMode: { EndScissorMode();break; } \
case OP_DrawTexture: { struct Texture a0=textures[rd_id(r)];int a1=rd_i32(r);int a2=rd_i32(r);struct Color a3=rd_Color(r);DrawTexture(a0,a1,a2,a3);break; } \
case OP_DrawTextureRec: { struct Texture a0=textures[rd_id(r)];struct Rectangle a1=rd_Rectangle(r);struct Vector2 a2=rd_Vector2(r);struct Color a3=rd_Color(r);DrawTextureRec(a0,a1,a2,a3);break; } \
case OP_DrawTexturePro: { struct Texture a0=textures[rd_id(r)];struct Rectangle a1=rd_Rectangle(r);struct Rectangle a2=rd_Rectangle(r);struct Vector2 a3=rd_Vector2(r);float a4=rd_float(r);struct Color a5=rd_Color(r);DrawTexturePro(a0,a1,a2,a3,a4,a5);break; } \
case OP_DrawTextureEx: { struct Texture a0=textures[rd_id(r)];struct Vector2 a1=rd_Vector2(r);float a2=rd_float(r);float a3=rd_float(r);struct Color a4=rd_Color(r);DrawTextureEx(a0,a1,a2,a3,a4);break; } \
case OP_DrawRectangle: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);struct Color a4=rd_Color(r);DrawRectangle(a0,a1,a2,a3,a4);break; } \
case OP_DrawRectangleRec: { struct Rectangle a0=rd_Rectangle(r);struct Color a1=rd_Color(r);DrawRectangleRec(a0,a1);break; } \
case OP_DrawRectanglePro: { struct Rectangle a0=rd_Rectangle(r);struct Vector2 a1=rd_Vector2(r);float a2=rd_float(r);struct Color a3=rd_Color(r);DrawRectanglePro(a0,a1,a2,a3);break; } \
case OP_DrawRectangleLines: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);struct Color a4=rd_Color(r);DrawRectangleLines(a0,a1,a2,a3,a4);break; } \
case OP_DrawRectangleLinesEx: { struct Rectangle a0=rd_Rectangle(r);float a1=rd_float(r);struct Color a2=rd_Color(r);DrawRectangleLinesEx(a0,a1,a2);break; } \
case OP_DrawCircle: { int a0=rd_i32(r);int a1=rd_i32(r);float a2=rd_float(r);struct Color a3=rd_Color(r);DrawCircle(a0,a1,a2,a3);break; } \
case OP_DrawCircleV: { struct Vector2 a0=rd_Vector2(r);float a1=rd_float(r);struct Color a2=rd_Color(r);DrawCircleV(a0,a1,a2);break; } \
case OP_DrawCircleGradient: { int a0=rd_i32(r);int a1=rd_i32(r);float a2=rd_float(r);struct Color a3=rd_Color(r);struct Color a4=rd_Color(r);DrawCircleGradient(a0,a1,a2,a3,a4);break; } \
case OP_DrawEllipse: { int a0=rd_i32(r);int a1=rd_i32(r);float a2=rd_float(r);float a3=rd_float(r);struct Color a4=rd_Color(r);DrawEllipse(a0,a1,a2,a3,a4);break; } \
case OP_DrawLine: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);struct Color a4=rd_Color(r);DrawLine(a0,a1,a2,a3,a4);break; } \
case OP_DrawLineV: { struct Vector2 a0=rd_Vector2(r);struct Vector2 a1=rd_Vector2(r);struct Color a2=rd_Color(r);DrawLineV(a0,a1,a2);break; } \
case OP_DrawLineEx: { struct Vector2 a0=rd_Vector2(r);struct Vector2 a1=rd_Vector2(r);float a2=rd_float(r);struct Color a3=rd_Color(r);DrawLineEx(a0,a1,a2,a3);break; } \
case OP_DrawTriangle: { struct Vector2 a0=rd_Vector2(r);struct Vector2 a1=rd_Vector2(r);struct Vector2 a2=rd_Vector2(r);struct Color a3=rd_Color(r);DrawTriangle(a0,a1,a2,a3);break; } \
case OP_DrawPixel: { int a0=rd_i32(r);int a1=rd_i32(r);struct Color a2=rd_Color(r);DrawPixel(a0,a1,a2);break; } \
case OP_DrawPixelV: { struct Vector2 a0=rd_Vector2(r);struct Color a1=rd_Color(r);DrawPixelV(a0,a1);break; } \
case OP_DrawText: { const char * a0=(const char *)rd_blob(r,NULL);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);struct Color a4=rd_Color(r);DrawText(a0,a1,a2,a3,a4);break; } \
case OP_DrawTextEx: { struct Font a0=fonts[rd_id(r)];const char * a1=(const char *)rd_blob(r,NULL);struct Vector2 a2=rd_Vector2(r);float a3=rd_float(r);float a4=rd_float(r);struct Color a5=rd_Color(r);DrawTextEx(a0,a1,a2,a3,a4,a5);break; } \
case OP_SetTextureFilter: { struct Texture a0=textures[rd_id(r)];int a1=rd_i32(r);SetTextureFilter(a0,a1);break; } \
case OP_SetTextureWrap: { struct Texture a0=textures[rd_id(r)];int a1=rd_i32(r);SetTextureWrap(a0,a1);break; } \
case OP_rlBegin: { int a0=rd_i32(r);rlBegin(a0);break; } \
case OP_rlEnd: { rlEnd();break; } \
case OP_rlColor4ub: { unsigned char a0=rd_i32(r);unsigned char a1=rd_i32(r);unsigned char a2=rd_i32(r);unsigned char a3=rd_i32(r);rlColor4ub(a0,a1,a2,a3);break; } \
case OP_rlNormal3f: { float a0=rd_float(r);float a1=rd_float(r);float a2=rd_float(r);rlNormal3f(a0,a1,a2);break; } \
case OP_rlTexCoord2f: { float a0=rd_float(r);float a1=rd_float(r);rlTexCoord2f(a0,a1);break; } \
case OP_rlVertex2f: { float a0=rd_float(r);float a1=rd_float(r);rlVertex2f(a0,a1);break; } \
case OP_rlVertex3f: { float a0=rd_float(r);float a1=rd_float(r);float a2=rd_float(r);rlVertex3f(a0,a1,a2);break; } \
case OP_rlPushMatrix: { rlPushMatrix();break; } \
case OP_rlPopMatrix: { rlPopMatrix();break; } \
case OP_rlTranslatef: { float a0=rd_float(r);float a1=rd_float(r);float a2=rd_float(r);rlTranslatef(a0,a1,a2);break; } \
case OP_rlScalef: { float a0=rd_float(r);float a1=rd_float(r);float a2=rd_float(r);rlScalef(a0,a1,a2);break; } \
case OP_rlRotatef: { float a0=rd_float(r);float a1=rd_float(r);float a2=rd_float(r);float a3=rd_float(r);rlRotatef(a0,a1,a2,a3);break; } \
case OP_rlDisableBackfaceCulling: { rlDisableBackfaceCulling();break; } \
case OP_rlEnableBackfaceCulling: { rlEnableBackfaceCulling();break; } \
case OP_rlDrawRenderBatchActive: { rlDrawRenderBatchActive();break; } \
case OP_rlSetBlendFactors: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);rlSetBlendFactors(a0,a1,a2);break; } \
case OP_rlSetBlendFactorsSeparate: { int a0=rd_i32(r);int a1=rd_i32(r);int a2=rd_i32(r);int a3=rd_i32(r);int a4=rd_i32(r);int a5=rd_i32(r);rlSetBlendFactorsSeparate(a0,a1,a2,a3,a4,a5);break; }
