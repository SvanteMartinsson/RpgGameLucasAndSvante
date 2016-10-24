import java.util.Scanner;

public class Input {
	
	Scanner scanner = new Scanner(System.in);
	int choise = 0;
	
	public void normalInput(){
		System.out.println("Display stats and xp: 1");
		System.out.println("Fight a random enemy: 2");
		System.out.println("Display inventory: 3");
		choise = scanner.nextInt();
		
		
		
	}
	
}
