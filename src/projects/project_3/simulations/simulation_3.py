"""
Module: simulation_3.py
---------------------
Analyse parallèle des logs du message broker STS.

Utilise le multiprocessing pour analyser efficacement les fichiers de log
générés par le système de messagerie, afin d'extraire des statistiques
et des indicateurs de performance.

Classes:
    LogAnalyzer: Classe d'analyse de fichiers log avec multiprocessing
    Simulation3: Classe principale de la simulation

Utilisation:
    python main.py --sim 3 [--duration 60]

Arguments:
    duration: Durée de l'analyse en secondes (défaut: 60)

Dépendances:
    - multiprocessing: Pour le traitement parallèle
    - matplotlib: Pour la génération de graphiques
    - colorama: Pour l'affichage en couleur dans la console

"""
import colorama
colorama.init()
import os
import re
import time
import json
import glob
import logging
import multiprocessing
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Any, Optional, Set

from src.ui.console_ui import ConsoleUI


class LogAnalyzer:
    """Classe d'analyse des logs du message broker"""
    
    def __init__(self, num_processes=None):
        """
        Initialise l'analyseur de logs
        
        Args:
            num_processes: Nombre de processus à utiliser (défaut: nombre de CPU)
        """
        self.num_processes = num_processes or multiprocessing.cpu_count()
        self.logger = logging.getLogger('log_analyzer')
    
    def find_latest_log_file(self) -> Optional[str]:
        """
        Trouve le fichier de log le plus récent du message broker
        
        Returns:
            Chemin du fichier le plus récent ou None si aucun fichier trouvé
        """
        log_dir = Path("logs")
        pattern = "message_broker_*.log"
        
        # Récupérer tous les fichiers correspondant au pattern
        log_files = list(log_dir.glob(pattern))
        
        if not log_files:
            self.logger.error("Aucun fichier de log du message broker trouvé")
            return None
        
        # Trier par date de modification (du plus récent au plus ancien)
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        latest_file = str(log_files[0])
        self.logger.info(f"Fichier de log le plus récent: {latest_file}")
        return latest_file
    
    def split_file_into_chunks(self, file_path: str, num_chunks: int) -> List[Tuple[int, int]]:
        """
        Divise un fichier en chunks pour traitement parallèle
        
        Args:
            file_path: Chemin du fichier à diviser
            num_chunks: Nombre de chunks souhaités
            
        Returns:
            Liste de tuples (position_début, position_fin) pour chaque chunk
        """
        file_size = os.path.getsize(file_path)
        chunk_size = max(1, file_size // num_chunks)
        
        chunks = []
        with open(file_path, 'r', encoding='utf-8') as f:
            start_pos = 0
            while start_pos < file_size:
                # Calculer la fin approximative du chunk
                end_pos = min(file_size, start_pos + chunk_size)
                
                # Si on n'est pas à la fin du fichier, trouver la fin de ligne
                if end_pos < file_size:
                    f.seek(end_pos)
                    # Lire jusqu'à la fin de la ligne
                    f.readline()
                    end_pos = f.tell()
                
                chunks.append((start_pos, end_pos))
                start_pos = end_pos
        
        self.logger.info(f"Fichier divisé en {len(chunks)} chunks")
        return chunks
    
    def process_chunk(self, args: Tuple[str, int, int]) -> Dict[str, Any]:
        """
        Traite un chunk du fichier de log
        
        Args:
            args: Tuple contenant (chemin_fichier, position_début, position_fin)
            
        Returns:
            Dictionnaire de statistiques pour ce chunk
        """
        file_path, start_pos, end_pos = args
        
        # Initialiser les compteurs et statistiques
        stats = {
            'message_types': Counter(),
            'senders': Counter(),
            'receivers': Counter(),
            'delivery_success': 0,
            'total_deliveries': 0,
            'timestamps': [],
            'message_content': defaultdict(list),
            'delivery_times': []
        }
        
        current_message = {
            'timestamp': None,
            'type': None,
            'sender': None
        }
        
        # Regex pour extraire les informations
        timestamp_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})'
        type_pattern = r'Type=([a-z_]+)'
        sender_pattern = r'Sender=([A-Za-z0-9_-]+)'
        receiver_pattern = r'Livraison du message à ([A-Za-z0-9_]+)'
        content_pattern = r"Message du contenu : ({.+}) livré avec succès"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Se positionner au début du chunk
                f.seek(start_pos)
                
                # Lire et traiter les lignes du chunk
                while f.tell() < end_pos:
                    line = f.readline()
                    if not line:
                        break
                    
                    try:
                        # Extraire le timestamp
                        timestamp_match = re.search(timestamp_pattern, line)
                        if timestamp_match:
                            timestamp_str = timestamp_match.group(1)
                            try:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                                stats['timestamps'].append(timestamp)
                                current_message['timestamp'] = timestamp
                            except ValueError:
                                # En cas d'erreur de parsing de date, continuer sans ajouter de timestamp
                                pass
                        
                        # Extraire le type de message
                        type_match = re.search(type_pattern, line)
                        if type_match:
                            msg_type = type_match.group(1)
                            stats['message_types'][msg_type] += 1
                            current_message['type'] = msg_type
                        
                        # Extraire l'expéditeur
                        sender_match = re.search(sender_pattern, line)
                        if sender_match:
                            sender = sender_match.group(1)
                            stats['senders'][sender] += 1
                            current_message['sender'] = sender
                        
                        # Extraire le destinataire
                        receiver_match = re.search(receiver_pattern, line)
                        if receiver_match:
                            receiver = receiver_match.group(1)
                            stats['receivers'][receiver] += 1
                            stats['total_deliveries'] += 1
                        
                        # Extraire le contenu et compter les livraisons réussies
                        content_match = re.search(content_pattern, line)
                        if content_match:
                            content_str = content_match.group(1)
                            try:
                                # Limiter la taille du contenu pour éviter les problèmes de mémoire
                                if len(content_str) > 10000:
                                    content_str = content_str[:10000] + "..."
                                
                                content = json.loads(content_str.replace("'", '"'))
                                
                                # Ne stocker que les premiers contenus de chaque type pour économiser la mémoire
                                if current_message['type'] and len(stats['message_content'][current_message['type']]) < 50:
                                    stats['message_content'][current_message['type']].append(content)
                            except json.JSONDecodeError:
                                # Si le contenu ne peut pas être parsé en JSON, l'ignorer
                                pass
                            except Exception:
                                # Ignorer les autres erreurs de parsing
                                pass
                            
                            stats['delivery_success'] += 1
                            
                            # Calculer le temps de livraison si on a un timestamp
                            if current_message['timestamp']:
                                try:
                                    delivery_time = (datetime.now() - current_message['timestamp']).total_seconds()
                                    if 0 <= delivery_time < 3600:  # Ignorer les temps aberrants (> 1h)
                                        stats['delivery_times'].append(delivery_time)
                                except Exception:
                                    # Ignorer les erreurs de calcul de temps
                                    pass
                    except Exception as e:
                        # Ignorer les erreurs de traitement d'une ligne particulière
                        logging.warning(f"Erreur lors du traitement d'une ligne: {e}")
                        continue
                        
        except Exception as e:
            logging.error(f"Erreur lors du traitement du chunk: {e}")
            
        # Limiter le nombre d'entrées dans les collections pour éviter les problèmes de mémoire
        stats['timestamps'] = stats['timestamps'][:10000]
        stats['delivery_times'] = stats['delivery_times'][:10000]
            
        return stats
    
    def merge_stats(self, all_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fusionne les statistiques de tous les chunks
        
        Args:
            all_stats: Liste des statistiques de chaque chunk
            
        Returns:
            Statistiques globales fusionnées
        """
        merged = {
            'message_types': Counter(),
            'senders': Counter(),
            'receivers': Counter(),
            'delivery_success': 0,
            'total_deliveries': 0,
            'timestamps': [],
            'message_content': defaultdict(list),
            'delivery_times': []
        }
        
        for stats in all_stats:
            merged['message_types'] += stats['message_types']
            merged['senders'] += stats['senders']
            merged['receivers'] += stats['receivers']
            merged['delivery_success'] += stats['delivery_success']
            merged['total_deliveries'] += stats['total_deliveries']
            merged['timestamps'].extend(stats['timestamps'])
            merged['delivery_times'].extend(stats['delivery_times'])
            
            for msg_type, contents in stats['message_content'].items():
                merged['message_content'][msg_type].extend(contents)
        
        # Trier les timestamps
        merged['timestamps'].sort()
        
        # Calculer des métriques supplémentaires
        if merged['total_deliveries'] > 0:
            merged['success_rate'] = (merged['delivery_success'] / merged['total_deliveries']) * 100
        else:
            merged['success_rate'] = 0
            
        if merged['timestamps']:
            start_time = merged['timestamps'][0]
            end_time = merged['timestamps'][-1]
            duration = (end_time - start_time).total_seconds()
            
            if duration > 0:
                merged['messages_per_second'] = len(merged['timestamps']) / duration
            else:
                merged['messages_per_second'] = 0
        else:
            merged['messages_per_second'] = 0
            
        if merged['delivery_times']:
            merged['avg_delivery_time'] = sum(merged['delivery_times']) / len(merged['delivery_times'])
            merged['max_delivery_time'] = max(merged['delivery_times'])
            merged['min_delivery_time'] = min(merged['delivery_times'])
            
        #TODO: Ajouter deux métriques supplémentaires. 
        
        return merged
    
    def analyze_log_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyse un fichier de log en utilisant le multiprocessing
        
        Args:
            file_path: Chemin du fichier à analyser
            
        Returns:
            Statistiques d'analyse du fichier
        """
        start_time = time.time()
        
        # Diviser le fichier en chunks
        # TODO utiliser split_file_into_chunks pour diviser le fichier en chunks
  
        
        # Préparer les arguments pour chaque processus
        # TODO mettre dans une liste les arguments pour chaque procesus
        
        # Traiter les chunks en parallèle
        # TODO : Écrire le code pour traiter les chunks en parallèle
        
        # Fusionner les résultats
        merged_stats = None # TODO: merger les résultats dans la variables merged_stats.
        
        # Ajouter des informations sur le traitement
        processing_time = time.time() - start_time
        merged_stats['processing_time'] = processing_time
        merged_stats['num_processes'] = self.num_processes
        merged_stats['file_size'] = os.path.getsize(file_path)
        
        self.logger.info(f"Analyse terminée en {processing_time:.2f} secondes avec {self.num_processes} processus")
        
        return merged_stats
    
    def generate_visualizations(self, stats: Dict[str, Any], output_dir: str = "logs") -> List[str]:
        """
        Génère des visualisations à partir des statistiques
        
        Args:
            stats: Statistiques d'analyse du fichier
            output_dir: Répertoire où sauvegarder les visualisations
            
        Returns:
            Liste des chemins des fichiers générés
        """
        output_files = []
        output_path = Path(output_dir) / "analysis"
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Graphique des types de messages
        if stats['message_types']:
            try:
                plt.figure(figsize=(12, 6))
                top_types = sorted(stats['message_types'].items(), key=lambda x: x[1], reverse=True)[:15]
                labels, values = zip(*top_types)
                safe_values = [min(int(v), 10**9) for v in values]
                
                plt.bar(labels, safe_values)
                plt.xticks(rotation=45, ha='right')
                plt.title('Distribution des types de messages')
                plt.tight_layout(pad=1.1)
                
                file_path = output_path / f"message_types_{timestamp}.png"
                plt.savefig(file_path)
                plt.close()
                output_files.append(str(file_path))
            except Exception as e:
                logging.warning(f"Erreur lors de la création du graphique des types de messages: {e}")
                plt.close()
        
        # 2. Graphique des expéditeurs
        if stats['senders']:
            try:
                plt.figure(figsize=(12, 6))
                top_senders = sorted(stats['senders'].items(), key=lambda x: x[1], reverse=True)[:10]
                
                if top_senders:
                    labels, values = zip(*top_senders)
                    safe_values = [min(int(v), 10**9) for v in values]
                    
                    plt.bar(labels, safe_values)
                    plt.xticks(rotation=45, ha='right')
                    plt.title('Top 10 des expéditeurs de messages')
                    plt.tight_layout(pad=1.1)
                    
                    file_path = output_path / f"senders_{timestamp}.png"
                    plt.savefig(file_path)
                    output_files.append(str(file_path))
                plt.close()
            except Exception as e:
                logging.warning(f"Erreur lors de la création du graphique des expéditeurs: {e}")
                plt.close()
        
        # 3. Graphique des destinataires
        if stats['receivers']:
            try:
                plt.figure(figsize=(12, 6))
                top_receivers = sorted(stats['receivers'].items(), key=lambda x: x[1], reverse=True)[:10]
                
                if top_receivers:
                    labels, values = zip(*top_receivers)
                    
                    # Convertir les valeurs en entiers standards
                    safe_values = [min(int(v), 10**9) for v in values]
                    
                    plt.bar(labels, safe_values)
                    plt.xticks(rotation=45, ha='right')
                    plt.title('Top 10 des destinataires de messages')
                    plt.tight_layout(pad=1.1)
                    
                    file_path = output_path / f"receivers_{timestamp}.png"
                    plt.savefig(file_path)
                    output_files.append(str(file_path))
                plt.close()
            except Exception as e:
                logging.warning(f"Erreur lors de la création du graphique des destinataires: {e}")
                plt.close()
        
        
        # 4. Graphique du taux de réussite
        try:
            plt.figure(figsize=(8, 8))
            labels = ['Succès', 'Échec']
            success = min(int(stats['delivery_success']), 10**9)
            total = min(int(stats['total_deliveries']), 10**9)
            failures = max(0, total - success)
            
            values = [success, failures]
            
            if sum(values) > 0:
                plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#4CAF50', '#F44336'])
                plt.title('Taux de réussite des livraisons de messages')
            else:
                plt.text(0.5, 0.5, "Pas de données de livraison disponibles", 
                       horizontalalignment='center', verticalalignment='center')
                plt.axis('off')
            
            file_path = output_path / f"success_rate_{timestamp}.png"
            plt.savefig(file_path)
            plt.close()
            output_files.append(str(file_path))
        except Exception as e:
            logging.warning(f"Erreur lors de la création du graphique de taux de réussite: {e}")
            plt.close()
        
        # 5. Graphique de l'activité au fil du temps
        if stats['timestamps']:
            plt.figure(figsize=(12, 6))
            
            try:
                dates = [dt for dt in stats['timestamps']]
                from collections import Counter
                rounded_times = [dt.replace(second=0, microsecond=0) for dt in dates]
                counts = Counter(rounded_times)
                

                plt.bar(counts.keys(), counts.values(), width=0.01)
                plt.gcf().autofmt_xdate()
                
                plt.xlabel('Temps')
                plt.ylabel('Nombre de messages')
                plt.title('Activité du broker de messages au fil du temps')
                
                # Formater l'axe des x
                from matplotlib.dates import DateFormatter
                ax = plt.gca()
                ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
                
                # Utiliser tight_layout avec des paramètres sécurisés
                plt.tight_layout(pad=1.1)
            except Exception as e:
                logging.warning(f"Erreur lors de la création du graphique d'activité: {e}")
                plt.clf()
                plt.text(0.5, 0.5, f"Impossible de générer le graphique d'activité:\n{str(e)}", 
                        horizontalalignment='center', verticalalignment='center')
                plt.axis('off')
            
            file_path = output_path / f"activity_{timestamp}.png"
            plt.savefig(file_path)
            plt.close()
            output_files.append(str(file_path))
        
        # Générer un rapport de synthèse
        report_path = output_path / f"analysis_report_{timestamp}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=== Rapport d'analyse des logs du message broker ===\n\n")
            f.write(f"Date de l'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Temps de traitement: {stats['processing_time']:.2f} secondes\n")
            f.write(f"Nombre de processus utilisés: {stats['num_processes']}\n")
            f.write(f"Taille du fichier analysé: {stats['file_size'] / 1024:.2f} KB\n\n")
            
            f.write("--- Statistiques générales ---\n")
            f.write(f"Nombre total de messages: {sum(stats['message_types'].values())}\n")
            f.write(f"Nombre d'expéditeurs uniques: {len(stats['senders'])}\n")
            f.write(f"Nombre de destinataires uniques: {len(stats['receivers'])}\n")
            f.write(f"Taux de réussite des livraisons: {stats['success_rate']:.2f}%\n")
            f.write(f"Messages par seconde: {stats['messages_per_second']:.2f}\n\n")
            
            if 'avg_delivery_time' in stats:
                f.write("--- Temps de livraison ---\n")
                f.write(f"Temps moyen de livraison: {stats['avg_delivery_time'] * 1000:.2f} ms\n")
                f.write(f"Temps maximum de livraison: {stats['max_delivery_time'] * 1000:.2f} ms\n")
                f.write(f"Temps minimum de livraison: {stats['min_delivery_time'] * 1000:.2f} ms\n\n")
            
            f.write("--- Types de messages ---\n")
            for msg_type, count in sorted(stats['message_types'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"{msg_type}: {count}\n")
            
            f.write("\n--- Top 10 des expéditeurs ---\n")
            for sender, count in sorted(stats['senders'].items(), key=lambda x: x[1], reverse=True)[:10]:
                f.write(f"{sender}: {count}\n")
            
            f.write("\n--- Top 10 des destinataires ---\n")
            for receiver, count in sorted(stats['receivers'].items(), key=lambda x: x[1], reverse=True)[:10]:
                f.write(f"{receiver}: {count}\n")
        
        output_files.append(str(report_path))
        
        return output_files


class Simulation3:
    """Simulation 3: Analyse parallèle des logs du message broker"""
    
    @staticmethod
    def run(duration=60):
        """
        Lance l'analyse des logs du message broker
        
        Args:
            duration: Durée maximale de l'analyse en secondes
        
        Returns:
            bool: True si l'analyse s'est bien déroulée, False sinon
        """
        try:
            # Affichage de l'en-tête
            ConsoleUI.print_header()
            
            # Utiliser directement les couleurs de colorama
            from colorama import Fore, Style
            print(f"{Fore.CYAN}Démarrage de l'analyse parallèle des logs du message broker...{Style.RESET_ALL}")
            
            # Configuration du logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(f"logs/simulation3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
                ]
            )
            
            # Création de l'analyseur de logs
            analyzer = LogAnalyzer()
            
            # Recherche du fichier de log le plus récent
            log_file = analyzer.find_latest_log_file()
            if not log_file:
                ConsoleUI.print_error("Aucun fichier de log du message broker trouvé")
                return False
            
            from colorama import Fore, Style
            print(f"Analyse du fichier: {log_file}")
            
            # Lancement de l'analyse
            start_time = time.time()
            
            # Démarrage du timer pour respecter la durée maximale
            end_time = start_time + duration
            
            # Exécution de l'analyse
            stats = analyzer.analyze_log_file(log_file)
            
            # Vérification du temps restant
            time_used = time.time() - start_time
            time_remaining = duration - time_used
            
            print(f"{Fore.GREEN}Analyse terminée en {time_used:.2f} secondes{Style.RESET_ALL}")
            
            print(f"{Fore.CYAN}Génération des visualisations...{Style.RESET_ALL}")
            output_files = analyzer.generate_visualizations(stats)
            
            print(f"{Fore.GREEN}{len(output_files)} fichiers générés:{Style.RESET_ALL}")
            for file_path in output_files:
                print(f"  - {file_path}")
                
            
            # Affichage des statistiques principales
            from colorama import Fore, Style
            print(f"\n{Fore.CYAN}Statistiques principales:{Style.RESET_ALL}")
            print(f"Nombre total de messages: {sum(stats['message_types'].values())}")
            print(f"Taux de réussite des livraisons: {stats['success_rate']:.2f}%")
            print(f"Messages par seconde: {stats['messages_per_second']:.2f}")
            
            if 'avg_delivery_time' in stats:
                print(f"Temps moyen de livraison: {stats['avg_delivery_time'] * 1000:.2f} ms")
            
            # Affichage des types de messages
            print(f"\n{Fore.CYAN}Distribution des types de messages:{Style.RESET_ALL}")
            for msg_type, count in sorted(stats['message_types'].items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {msg_type}: {count}")
            
            ConsoleUI.print_success("Analyse terminée avec succès")
            return True
            
        except Exception as e:
            ConsoleUI.print_error(f"Erreur lors de l'analyse: {str(e)}")
            logging.error(f"Erreur détaillée:", exc_info=True)
            return False


if __name__ == "__main__":
    # Exécution directe (pour les tests)
    Simulation3.run(duration=120)