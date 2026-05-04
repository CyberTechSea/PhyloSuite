# Installing External Tools

PhyloSuite works out of the box with its built-in Python engine.  
For publication-quality results, install these tools and add them to your PATH.

---

## ModelTest-NG

**Purpose**: ML-optimized model selection (1624 models, full precision)

### Linux / macOS
```bash
# Download pre-compiled binary from GitHub releases
wget https://github.com/ddarriba/modeltest/releases/latest/download/modeltest-ng-linux.tar.gz
tar -xzf modeltest-ng-linux.tar.gz
sudo mv modeltest-ng /usr/local/bin/
```

### Windows
Download `modeltest-ng-win.exe` from https://github.com/ddarriba/modeltest/releases  
Rename to `modeltest-ng.exe` and place in `C:\Windows\System32\` or add the folder to PATH.

### Verify
```bash
modeltest-ng --version
```

---

## IQ-TREE 2

**Purpose**: Maximum likelihood phylogenetic inference with ultrafast bootstrap

### Linux
```bash
wget https://github.com/iqtree/iqtree2/releases/latest/download/iqtree2-linux-intel.tar.gz
tar -xzf iqtree2-*.tar.gz
sudo cp iqtree2-*/bin/iqtree2 /usr/local/bin/
```

### macOS
```bash
brew install iqtree2
```

### Windows
Download from http://www.iqtree.org/#download and add to PATH.

### Verify
```bash
iqtree2 --version
```

---

## MAFFT (alignment)

### Linux
```bash
sudo apt install mafft           # Debian/Ubuntu
sudo dnf install mafft           # Fedora
```

### macOS
```bash
brew install mafft
```

### Windows
Download installer from https://mafft.cbrc.jp/alignment/software/

---

## MUSCLE (alternative aligner)

### Linux
```bash
sudo apt install muscle
```

### macOS
```bash
brew install muscle
```

### Windows
Download from https://www.drive5.com/muscle/downloads.htm

---

## Verifying tool detection

After installation, open PhyloSuite and check the status indicator in the bottom-left corner of the sidebar.

- **Green dot**: All detected tools ready  
- **Yellow dot**: Some tools found  
- **Red dot**: No external tools (built-in engine will be used)

You can also call `/health` in the API for a JSON summary of detected tools.
