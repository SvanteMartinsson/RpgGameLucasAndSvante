import java.util.Scanner;

public class Input {
	
	Scanner scanner = new Scanner(System.in);
	int choise = 0;
	
	public void normalInput(){
		System.out.println("Display stats: 1");
		System.out.println("Fight a random enemy: 2");
		System.out.println("");
		choise = scanner.nextInt();
		
		
		
	}
	
}
