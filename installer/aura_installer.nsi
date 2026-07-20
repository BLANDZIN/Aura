; ═══════════════════════════════════════════════════════════════════════════════
; AURA V11 — NSIS Installer (Windows)
; ====================================
; Cria instalador profissional com wizard, atalhos e desinstalador.
;
; Pré-requisito: ter rodado build_windows.bat primeiro (AURA.exe em dist/AURA)
;
; Uso:
;   makensis aura_installer.nsi
;
; Saída:
;   dist/AURA_V11_Setup.exe
; ═══════════════════════════════════════════════════════════════════════════════

; ── Configuração do instalador ────────────────────────────────────────────────
Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Metadados
!define PRODUCT_NAME         "AURA"
!define PRODUCT_VERSION      "11.0.0"
!define PRODUCT_PUBLISHER    "AURA Project"
!define PRODUCT_WEB_SITE     "https://github.com/BLANDZIN/Aura"
!define PRODUCT_DIR_REGKEY   "Software\Microsoft\Windows\CurrentVersion\App Paths\AURA.exe"
!define PRODUCT_UNINST_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT  "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

; Compressão
SetCompressor /SOLID lzma
SetCompressorDictSize 32

; Interface
!define MUI_ABORTWARNING
!define MUI_ICON            "..\assets\aura.ico"
!define MUI_UNICON          "..\assets\aura.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\assets\welcome.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "..\assets\header.bmp"

; ── Páginas ───────────────────────────────────────────────────────────────────
; Instalação
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Desinstalação
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Idioma
!insertmacro MUI_LANGUAGE "PortugueseBR"
!insertmacro MUI_LANGUAGE "English"

; ── Nomes ─────────────────────────────────────────────────────────────────────
Name             "${PRODUCT_NAME} V${PRODUCT_VERSION}"
OutFile          "..\AURA_V11_Setup.exe"
InstallDir       "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails  show
ShowUninstDetails show

; ── Seção principal ───────────────────────────────────────────────────────────
Section "AURA (obrigatório)" SecCore
    SectionIn RO
    SetOutPath "$INSTDIR"

    ; ══ Arquivos do programa ══════════════════════════════════════════════════
    File /r "..\dist\AURA\*"

    ; ══ Cria pastas de dados ═════════════════════════════════════════════════
    CreateDirectory "$INSTDIR\models"
    CreateDirectory "$INSTDIR\extensions"
    CreateDirectory "$INSTDIR\profiles"
    CreateDirectory "$INSTDIR\cache"
    CreateDirectory "$INSTDIR\workspace"
    CreateDirectory "$INSTDIR\logs"
    CreateDirectory "$INSTDIR\database"
    CreateDirectory "$INSTDIR\themes"
    CreateDirectory "$INSTDIR\voices"

    ; ══ Registro no Windows ═══════════════════════════════════════════════════
    WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}"   ""           "$INSTDIR\AURA.exe"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "DisplayName"     "${PRODUCT_NAME} V${PRODUCT_VERSION}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "DisplayIcon"     "$INSTDIR\AURA.exe,0"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "DisplayVersion"  "${PRODUCT_VERSION}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "Publisher"       "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "${PRODUCT_UNINST_KEY}"   "URLInfoAbout"    "${PRODUCT_WEB_SITE}"
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoModify"        1
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoRepair"        1

    ; ══ Desinstalador ═════════════════════════════════════════════════════════
    WriteUninstaller "$INSTDIR\uninst.exe"

    ; ══ Atalhos ═══════════════════════════════════════════════════════════════
    ; Menu Iniciar
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut  "$SMPROGRAMS\${PRODUCT_NAME}\AURA.lnk"       "$INSTDIR\AURA.exe"
    CreateShortCut  "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar.lnk" "$INSTDIR\uninst.exe"

    ; Área de Trabalho
    CreateShortCut  "$DESKTOP\AURA.lnk"  "$INSTDIR\AURA.exe"

    ; ══ Tamanho estimado ═════════════════════════════════════════════════════
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"

SectionEnd

; ── Seção: Atalho no Menu de Contexto (opcional) ─────────────────────────────
Section "Menu de Contexto" SecContext
    ; Adiciona \"Perguntar à AURA\" no menu de contexto de arquivos .txt
    WriteRegStr HKCR "txtfile\shell\AURA_Ask"        "" "Perguntar à AURA..."
    WriteRegStr HKCR "txtfile\shell\AURA_Ask\command" "" '"$INSTDIR\AURA.exe" "%1"'
SectionEnd

; ── Seção: Verificação do Ollama ─────────────────────────────────────────────
Section "Verificar Ollama" SecOllama
    ; Avisa o usuário se o Ollama parece não estar instalado
    IfFileExists "$PROGRAMFILES\Ollama\ollama.exe" ollama_found
    IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" ollama_found
    MessageBox MB_ICONINFORMATION|MB_OK \
        "⚠️  Ollama não foi encontrado.$\n$\n\
        A AURA precisa do Ollama para funcionar.$\n$\n\
        Baixe em: https://ollama.com/download$\n\
        Depois instale pelo menos um modelo:$\n\
        ollama pull qwen2.5:3b"
    ollama_found:
SectionEnd

; ── Descrições das seções ────────────────────────────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecCore}    "Arquivos principais da AURA. Instalação obrigatória."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecContext}  "Adiciona 'Perguntar à AURA' no menu de contexto do Windows."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecOllama}   "Verifica se o Ollama está instalado e orienta o usuário."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Desinstalação ─────────────────────────────────────────────────────────────
Section Uninstall
    ; Remove atalhos
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\AURA.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar.lnk"
    RMDir  "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete "$DESKTOP\AURA.lnk"

    ; Remove menu de contexto
    DeleteRegKey HKCR "txtfile\shell\AURA_Ask"

    ; Remove registro
    DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"

    ; Remove arquivos (NÃO remove models/ — o usuário pode ter modelos grandes)
    Delete "$INSTDIR\AURA.exe"
    Delete "$INSTDIR\uninst.exe"
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\config"
    Delete "$INSTDIR\LEIAME.txt"

    ; Pastas que podem ter dados do usuário — pergunta se remove
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Deseja remover TODOS os dados da AURA?$\n$\n\
        Isso inclui: modelos baixados, extensões, perfis, cache e logs.$\n\
        Clique em NÃO para manter seus dados." \
        IDNO skip_data_removal

    RMDir /r "$INSTDIR\models"
    RMDir /r "$INSTDIR\extensions"
    RMDir /r "$INSTDIR\profiles"
    RMDir /r "$INSTDIR\cache"
    RMDir /r "$INSTDIR\workspace"
    RMDir /r "$INSTDIR\logs"
    RMDir /r "$INSTDIR\database"
    RMDir /r "$INSTDIR\themes"
    RMDir /r "$INSTDIR\voices"

    skip_data_removal:
    RMDir "$INSTDIR"
SectionEnd

; ── Funções ───────────────────────────────────────────────────────────────────
Function .onInit
    ; Verifica se já está instalado
    ReadRegStr $0 HKLM "${PRODUCT_UNINST_KEY}" "UninstallString"
    ${If} $0 != ""
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "AURA já está instalada.$\n$\n\
            Deseja sobrescrever a instalação existente?" \
            IDYES continue_install
        Abort
        continue_install:
    ${EndIf}
FunctionEnd

Function .onInstSuccess
    ; Oferece iniciar a AURA
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "✅ AURA V${PRODUCT_VERSION} instalada com sucesso!$\n$\n\
        Deseja iniciar a AURA agora?" \
        IDNO no_launch
    Exec '"$INSTDIR\AURA.exe"'
    no_launch:
FunctionEnd
