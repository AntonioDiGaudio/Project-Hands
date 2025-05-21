import time
from collections import defaultdict
import statistics
import threading

class SimpleProfiler:
    """
    Profiler semplice per misurare i tempi di esecuzione di diverse parti del codice.
    """
    def __init__(self):
        self.timings = defaultdict(list)
        self.start_times = {}
        self.lock = threading.Lock()
        self.enabled = True
        self.max_samples = 100  # Numero massimo di campioni da conservare per sezione
    
    def start(self, section_name):
        """Inizia a misurare il tempo per una sezione"""
        if not self.enabled:
            return
        self.start_times[section_name] = time.time()
    
    def stop(self, section_name):
        """Termina la misurazione per una sezione e registra il tempo"""
        if not self.enabled or section_name not in self.start_times:
            return 0
        
        elapsed = (time.time() - self.start_times[section_name]) * 1000  # ms
        with self.lock:
            self.timings[section_name].append(elapsed)
            # Limita il numero di campioni
            if len(self.timings[section_name]) > self.max_samples:
                self.timings[section_name].pop(0)
        
        return elapsed
    
    def get_avg_time(self, section_name):
        """Restituisce il tempo medio per una sezione"""
        with self.lock:
            times = self.timings.get(section_name, [])
            if not times:
                return 0
            return sum(times) / len(times)
    
    def get_stats(self):
        """Restituisce statistiche per tutte le sezioni misurate"""
        stats = {}
        with self.lock:
            for section, times in self.timings.items():
                if not times:
                    continue
                stats[section] = {
                    'count': len(times),
                    'avg': statistics.mean(times),
                    'min': min(times),
                    'max': max(times),
                    'median': statistics.median(times),
                    'total': sum(times)
                }
        return stats
    
    def print_stats(self):
        """Stampa le statistiche in formato leggibile"""
        stats = self.get_stats()
        if not stats:
            print("Nessuna statistica disponibile")
            return
        
        print("\n=== STATISTICHE DI PROFILING ===")
        print(f"{'Sezione':<30} {'Count':<8} {'Media (ms)':<12} {'Min (ms)':<10} {'Max (ms)':<10} {'Mediana (ms)':<12}")
        print("-" * 90)
        
        # Ordina per tempo medio (dal più lento al più veloce)
        for section, data in sorted(stats.items(), key=lambda x: x[1]['avg'], reverse=True):
            print(f"{section:<30} {data['count']:<8} {data['avg']:<12.2f} {data['min']:<10.2f} {data['max']:<10.2f} {data['median']:<12.2f}")
    
    def reset(self):
        """Resetta tutte le statistiche"""
        with self.lock:
            self.timings.clear()
            self.start_times.clear()

# Crea un'istanza globale del profiler
profiler = SimpleProfiler()

# Classe per utilizzare il profiler con il context manager (with)
class ProfileSection:
    def __init__(self, section_name):
        self.section_name = section_name
    
    def __enter__(self):
        profiler.start(self.section_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        profiler.stop(self.section_name)
